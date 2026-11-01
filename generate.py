"""Parametric solid CAD; run with uv run generate.py. Units: mm."""
import json
import struct
import zlib
from pathlib import Path
import numpy as np
import trimesh as tm

ROOT = Path(__file__).resolve().parent
P = json.loads((ROOT / "dimensions.json").read_text())
OUT = ROOT / "print"
OUT.mkdir(exist_ok=True)
C, T, F = (P[k] for k in ("clearance_per_side", "wall", "floor"))
W = max(P["keyboard_width"], P["phone_width"]) + 2*(C+T)
D = max(P["keyboard_depth"], P["phone_depth"]) + 2*(C+T)
HK = F + P["keyboard_thickness"] + P["face_recess"]
HP = F + P["phone_thickness"] + P["face_recess"]
AY = D + P["hinge_offset"]

def box(x, y, z, dx, dy, dz):
    m = tm.creation.box(extents=[dx, dy, dz])
    m.apply_translation([x+dx/2, y+dy/2, z+dz/2])
    return m

def union(parts):
    return tm.boolean.union(parts, engine="manifold")

def subtract(body, cuts):
    return tm.boolean.difference([body]+cuts, engine="manifold")

def mirror_y(m):
    matrix = np.eye(4)
    matrix[1,1], matrix[1,3] = -1, D
    return m.copy().apply_transform(matrix)

def lattice_cuts(phone=False):
    radius=P['mesh_hole_radius']
    pitch_radius=radius+P['mesh_web_width']/np.sqrt(3)
    edge=P['back_frame_width']
    strip=P['mounting_strip_width']
    cuts=[]
    for column,cx in enumerate(np.arange(edge+radius,W-edge,1.5*pitch_radius)):
        if cx+radius>W-edge:
            continue
        if any(abs(cx-rail)<radius+strip/2 for rail in [W/3,2*W/3]):
            continue
        for cy in np.arange(edge+radius+(column%2)*np.sqrt(3)*pitch_radius/2,D-edge,np.sqrt(3)*pitch_radius):
            if cy+radius>D-edge:
                continue
            if phone:
                camera_x=(W-P['phone_width']-2*C)/2+2
                camera_y=D-T-P['phone_depth']-C+P['camera_opening_edge_margin']
                camera_depth=P['phone_depth']-2*P['camera_opening_edge_margin']
                if (cx+radius>camera_x-2 and cx-radius<camera_x+P['camera_opening_width']+2
                    and cy+radius>camera_y-2 and cy-radius<camera_y+camera_depth+2):
                    continue
            hole=tm.creation.cylinder(radius=radius,height=F+2,sections=6)
            hole.apply_translation([cx,cy,F/2])
            cuts.append(hole)
    return cuts

def tray(phone=False):
    H = HP if phone else HK
    w, d, thick = (P[f"{'phone' if phone else 'keyboard'}_{k}"] for k in ("width", "depth", "thickness"))
    outer_w,outer_d = W,D
    outer_x,outer_y = 0,0
    x, y = (W-w-2*C)/2,D-T-d-2*C
    seat = H-P["face_recess"]-thick
    # Separate shell depths eliminate the raised phone seat.
    shell = subtract(box(outer_x,outer_y,0,outer_w,outer_d,H), [box(x,y,seat,w+2*C,d+2*C,H)])
    cuts = lattice_cuts(phone)
    if phone:
        # Generous camera/flash window across the camera end, leaving a frame.
        # Broad coverage supports either landscape orientation without assuming
        # unmeasured lens/flash centre coordinates.
        margin = P["camera_opening_edge_margin"]
        cuts.append(box(x+2,y+C+margin,-1,
                        P["camera_opening_width"],d-2*margin,seat+1.01))
    else:
        # Hollow the spacer ahead of the shorter keyboard; retain a thin locator
        # wall at its front edge and a matching outer perimeter for closure.
        if y>2*T:
            cuts.append(box(T,T,F,W-2*T,y-2*T,H))
    # Broad access windows avoid guessed button and connector coordinates.
    # Keep the hinge-side wall intact to anchor the small barrel webs.
    for yy in [outer_y-1]:
        cuts.append(box(x+18,yy,seat+2,w+2*C-36,y+1,H))
    for xx in [outer_x-1, x+w+2*C]:
        cuts.append(box(xx,y+d/2-12,seat+1,(W-w-2*C)/2+1,24,H))
    shell = subtract(shell,cuts)
    # Compact round knuckles at the closing plane; local supports under barrels.
    pitch = (W-12)/5
    knuckles = []
    for i in range(5):
        if (i%2 == 1) != phone:
            continue
        a = 6+i*pitch+P["hinge_gap"]/2
        length = pitch-P["hinge_gap"]
        radius = P["hinge_radius"]
        web = box(a,D-0.4,H-radius,length,AY-D+0.4,radius)
        barrel = tm.creation.cylinder(radius=radius,height=length,sections=64)
        barrel.apply_transform(tm.transformations.rotation_matrix(np.pi/2,[0,1,0]))
        barrel.apply_translation([a+length/2,AY,H])
        block = union([web,barrel])
        bore = tm.creation.cylinder(radius=P["hinge_bore"]/2,height=length+2,sections=48)
        bore.apply_transform(tm.transformations.rotation_matrix(np.pi/2,[0,1,0]))
        bore.apply_translation([a+length/2,AY,H])
        knuckles.append(subtract(block,[bore]))
    result = union([shell]+knuckles)
    return mirror_y(result) if phone else result

def export(name, mesh):
    assert mesh.is_watertight and mesh.is_volume, name
    parents = list(range(len(mesh.vertices)))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    for a,b,c in mesh.faces:
        parents[root(int(b))] = root(int(a))
        parents[root(int(c))] = root(int(a))
    assert len({root(i) for i in range(len(parents))}) == 1, f"Disconnected solid: {name}"
    mesh.export(OUT/f"{name}.stl")
    return {"bounds_mm":mesh.bounds.round(3).tolist(),"volume_mm3":round(mesh.volume,1),"watertight":True,"solid_count":1}

def pose(lid, angle):
    m = lid.copy()
    m.apply_transform(tm.transformations.rotation_matrix(np.pi,[1,0,0]))
    m.apply_translation([0,D,HK+HP])
    m.apply_transform(tm.transformations.rotation_matrix(-np.deg2rad(angle),[1,0,0],point=[0,AY,HK]))
    return m

def device_body(phone=False):
    name='phone' if phone else 'keyboard'
    w,d,t=(P[f'{name}_{key}'] for key in ('width','depth','thickness'))
    body=box((W-w)/2,D-T-C-d,F,w,d,t)
    return mirror_y(body) if phone else body

def render_preview(meshes, stem):
    (ROOT/stem).parent.mkdir(parents=True,exist_ok=True)
    # Orthographic preview of the actual exported solids, sorted back to front.
    view=np.array([[0.85,0.52,0],[0.26,-0.43,-0.86],[0.45,-0.73,0.50]])
    polygons=[]
    all_points=[]
    for mesh,color in meshes:
        points=mesh.vertices @ view.T
        all_points.extend(points[:,:2])
        for face,normal in zip(mesh.faces,mesh.face_normals):
            tri=points[face]
            shade=0.55+0.45*max(0,float(normal @ np.array([-0.3,-0.4,0.866])))
            shaded='#'+''.join(f'{int(int(color[i:i+2],16)*shade):02x}' for i in (1,3,5))
            polygons.append((tri[:,2].mean(),tri,shaded))
    low=np.min(all_points,axis=0)-8
    high=np.max(all_points,axis=0)+8
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{low[0]} {low[1]} {high[0]-low[0]} {high[1]-low[1]}">']
    svg.append(f'<rect x="{low[0]}" y="{low[1]}" width="{high[0]-low[0]}" height="{high[1]-low[1]}" fill="#f2f5f7"/>')
    for _,tri,color in sorted(polygons,key=lambda p:p[0]):
        coords=' '.join(f'{x:.3f},{y:.3f}' for x,y in tri[:,:2])
        svg.append(f'<polygon points="{coords}" fill="{color}" stroke="#22313a" stroke-width="0.08"/>')
    svg.append('</svg>')
    (ROOT/f'{stem}.svg').write_text('\n'.join(svg))
    scale=1400/max(high-low)
    size=np.ceil((high-low)*scale).astype(int)
    pixels=np.full((size[1],size[0],3),245,dtype=np.uint8)
    depth=np.full((size[1],size[0]),-np.inf)
    for _,tri,color in sorted(polygons,key=lambda p:p[0]):
        zz=tri[:,2]
        tri=(tri[:,:2]-low)*scale
        left,top=np.maximum(np.floor(tri.min(axis=0)).astype(int),0)
        right,bottom=np.minimum(np.ceil(tri.max(axis=0)).astype(int),size-1)
        xx,yy=np.meshgrid(np.arange(left,right+1),np.arange(top,bottom+1))
        signs=[]
        for a,b in zip(tri,np.roll(tri,-1,axis=0)):
            signs.append((xx-a[0])*(b[1]-a[1])-(yy-a[1])*(b[0]-a[0]))
        mask=(np.min(signs,axis=0)>=0)|(np.max(signs,axis=0)<=0)
        denom=signs[0][0,0]+signs[1][0,0]+signs[2][0,0]
        if abs(denom)<1e-9:
            continue
        z=(signs[1]*zz[0]+signs[2]*zz[1]+signs[0]*zz[2])/denom
        current_depth=depth[top:bottom+1,left:right+1]
        mask &= z>current_depth
        current_depth[mask]=z[mask]
        rgb=[int(color[i:i+2],16) for i in (1,3,5)]
        pixels[top:bottom+1,left:right+1][mask]=rgb
    def chunk(kind,data):
        return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data))
    raw=b''.join(b'\x00'+row.tobytes() for row in pixels)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',*size,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
    (ROOT/f'{stem}.png').write_bytes(png)

def main():
    base, lid = tray(), tray(True)
    closed=pose(lid,0)
    assert np.allclose(base.bounds[:,:2],closed.bounds[:,:2],atol=1e-5), 'Closed outlines differ'
    report = {"assumption":"UNCONFIRMED Rii K06, 151 x 59 x 11 mm", "tray_heights_mm":{"keyboard":HK,"phone":HP},"closed_printed_envelope_mm":[W,AY+P["hinge_radius"],HK+HP],"camera_projection_beyond_frame_mm":max(0,P["camera_allowance"]-F),"parts":{}}
    report['matching_closed_footprints']=True
    for name,m in [("keyboard_tray",base),("phone_tray",lid)]:
        report["parts"][name]=export(name,m)
    # Full footprint, shallow gauges: cheap check of the actual pocket dimensions.
    for phone in [False,True]:
        name = "phone" if phone else "keyboard"
        w,d = P[name+"_width"]+2*C,P[name+"_depth"]+2*C
        gauge = subtract(box(0,0,0,w+2*T,d+2*T,3),[box(T,T,-1,w,d,5)])
        report["parts"][name+"_fit_gauge"]=export(name+"_fit_gauge",gauge)
    # Simple independent hinge-bore coupon, matching the production cross-section.
    block = box(0,0,0,16,8,8)
    bore = tm.creation.cylinder(radius=P["hinge_bore"]/2,height=18,sections=48)
    bore.apply_transform(tm.transformations.rotation_matrix(np.pi/2,[0,1,0]))
    bore.apply_translation([8,4,4])
    report["parts"]["hinge_bore_gauge"] = export("hinge_bore_gauge",subtract(block,[bore]))
    coupon=tm.boolean.intersection([base,box(6.25,D-2,-1,16,AY-D+P['hinge_radius']+3,HK+P['hinge_radius']+2)],engine='manifold')
    report['parts']['hinge_print_coupon']=export('hinge_print_coupon',coupon)
    collisions=[]
    loaded_collisions=[]
    loaded_base=union([base,device_body()])
    loaded_lid=union([lid,device_body(True)])
    for angle in range(0,181):
        intersection=tm.boolean.intersection([base,pose(lid,angle)],engine="manifold")
        with np.errstate(divide='ignore',invalid='ignore'):
            volume=abs(intersection.volume) if not intersection.is_empty else 0
        if volume>0.01: collisions.append([angle,round(volume,4)])
        overlap=tm.boolean.intersection([loaded_base,pose(loaded_lid,angle)],engine='manifold')
        with np.errstate(divide='ignore',invalid='ignore'):
            occupied_volume=abs(overlap.volume) if not overlap.is_empty else 0
        if occupied_volume>0.01: loaded_collisions.append([angle,round(occupied_volume,4)])
    report["hinge_sweep_collisions"] = collisions
    report["hinge_sweep_step_degrees"] = 1
    report["total_printed_volume_mm3"] = round(base.volume+lid.volume,1)
    report["device_body_sweep_collisions"] = loaded_collisions
    assert not collisions, f"Hinge collisions: {collisions}"
    assert not loaded_collisions, f"Device body collisions: {loaded_collisions}"
    scene=tm.Scene()
    base.visual.vertex_colors=np.tile([65,85,95,255],(len(base.vertices),1))
    opened=pose(lid,110)
    opened.visual.vertex_colors=np.tile([60,150,160,255],(len(opened.vertices),1))
    scene.add_geometry(base,node_name="keyboard_tray")
    scene.add_geometry(opened,node_name="phone_tray")
    scene.export(str(ROOT/"assembly.glb"))
    render_preview([(base,'#41555f'),(opened,'#3c96a0')], 'docs/minimal-open')
    render_preview([(base,'#41555f'),(pose(lid,0),'#3c96a0')], 'docs/minimal-closed')
    (ROOT/'preview.png').write_bytes((ROOT/'docs/minimal-open.png').read_bytes())
    (ROOT/'preview.svg').write_text((ROOT/'docs/minimal-open.svg').read_text())
    (ROOT/"validation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__ == "__main__":
    main()
