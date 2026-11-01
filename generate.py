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
H = F + max(P["keyboard_thickness"], P["phone_thickness"]+P["camera_allowance"]) + P["face_recess"]
AY = D + H + 5

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

def tray(phone=False):
    w, d, thick = (P[f"{'phone' if phone else 'keyboard'}_{k}"] for k in ("width", "depth", "thickness"))
    x, y = (W-w-2*C)/2, (D-d-2*C)/2
    seat = H-P["face_recess"]-thick
    # Solid pad supports the device; camera end relieved to the bottom skin.
    shell = subtract(box(0,0,0,W,D,H), [box(x,y,seat,w+2*C,d+2*C,H)])
    cuts = []
    if phone:
        cuts.append(box(x,y,F,36,d+2*C,seat-F+0.01))
    # Broad access windows avoid guessed button and connector coordinates.
    for yy in [-1, y+d+2*C]:
        cuts.append(box(x+18,yy,seat+2,w+2*C-36,D-d,H))
    for xx in [-1, x+w+2*C]:
        cuts.append(box(xx,y+d/2-12,seat+1,W-w,24,H))
    shell = subtract(shell,cuts)
    # Five alternating knuckles. Rectangular bottoms sit directly on the bed.
    pitch = (W-12)/5
    knuckles = []
    for i in range(5):
        if (i%2 == 1) != phone:
            continue
        a = 6+i*pitch+P["hinge_gap"]/2
        length = pitch-P["hinge_gap"]
        web = box(a,D-0.6,0,length,AY-D+0.6,H-4)
        block = union([web,box(a,AY-4,0,length,8,H+4)])
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
    m.apply_translation([0,D,2*H])
    m.apply_transform(tm.transformations.rotation_matrix(-np.deg2rad(angle),[1,0,0],point=[0,AY,H]))
    return m

def main():
    base, lid = tray(), tray(True)
    report = {"assumption":"UNCONFIRMED Rii K06, 151 x 59 x 11 mm", "outer_tray_mm":[W,D,H],"closed_envelope_mm":[W,AY+4,2*H],"parts":{}}
    for name,m in [("keyboard_tray",base),("phone_tray",lid)]:
        report["parts"][name]=export(name,m)
    # Full footprint, shallow gauges: cheap check of the actual pocket dimensions.
    for phone in [False,True]:
        name = "phone" if phone else "keyboard"
        w,d = P[name+"_width"]+2*C,P[name+"_depth"]+2*C
        gauge = subtract(box(0,0,0,w+2*T,d+2*T,3),[box(T,T,-1,w,d,5)])
        report["parts"][name+"_fit_gauge"]=export(name+"_fit_gauge",gauge)
    # Simple independent hinge-bore coupon, matching the production cross-section.
    block = box(0,0,0,16,8.6,H+4)
    bore = tm.creation.cylinder(radius=P["hinge_bore"]/2,height=18,sections=48)
    bore.apply_transform(tm.transformations.rotation_matrix(np.pi/2,[0,1,0]))
    bore.apply_translation([8,4.6,H])
    report["parts"]["hinge_bore_gauge"] = export("hinge_bore_gauge",subtract(block,[bore]))
    collisions=[]
    for angle in range(0,181,5):
        intersection=tm.boolean.intersection([base,pose(lid,angle)],engine="manifold")
        volume=abs(intersection.volume) if not intersection.is_empty else 0
        if volume>0.01: collisions.append([angle,round(volume,4)])
    report["hinge_sweep_collisions"] = collisions
    assert not collisions, f"Hinge collisions: {collisions}"
    scene=tm.Scene()
    base.visual.vertex_colors=np.tile([65,85,95,255],(len(base.vertices),1))
    opened=pose(lid,110)
    opened.visual.vertex_colors=np.tile([60,150,160,255],(len(opened.vertices),1))
    scene.add_geometry(base,node_name="keyboard_tray")
    scene.add_geometry(opened,node_name="phone_tray")
    scene.export(str(ROOT/"assembly.glb"))
    # Orthographic preview of the actual exported solids, sorted back to front.
    view=np.array([[0.85,0.52,0],[0.26,-0.43,-0.86],[0.45,-0.73,0.50]])
    polygons=[]
    all_points=[]
    for mesh,color in [(base,'#41555f'),(opened,'#3c96a0')]:
        points=mesh.vertices @ view.T
        all_points.extend(points[:,:2])
        for face,normal in zip(mesh.faces,mesh.face_normals):
            tri=points[face]
            shade=0.55+0.45*max(0,float(normal @ np.array([-0.3,-0.4,0.866])))
            shaded='#'+''.join(f'{int(int(color[i:i+2],16)*shade):02x}' for i in (1,3,5))
            polygons.append((tri[:,2].mean(),tri[:,:2],shaded))
    low=np.min(all_points,axis=0)-8
    high=np.max(all_points,axis=0)+8
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{low[0]} {low[1]} {high[0]-low[0]} {high[1]-low[1]}">']
    svg.append(f'<rect x="{low[0]}" y="{low[1]}" width="{high[0]-low[0]}" height="{high[1]-low[1]}" fill="#f2f5f7"/>')
    for _,tri,color in sorted(polygons,key=lambda p:p[0]):
        coords=' '.join(f'{x:.3f},{y:.3f}' for x,y in tri)
        svg.append(f'<polygon points="{coords}" fill="{color}" stroke="#22313a" stroke-width="0.08"/>')
    svg.append('</svg>')
    (ROOT/'preview.svg').write_text('\n'.join(svg))
    scale=800/max(high-low)
    size=np.ceil((high-low)*scale).astype(int)
    pixels=np.full((size[1],size[0],3),245,dtype=np.uint8)
    for _,tri,color in sorted(polygons,key=lambda p:p[0]):
        tri=(tri-low)*scale
        left,top=np.maximum(np.floor(tri.min(axis=0)).astype(int),0)
        right,bottom=np.minimum(np.ceil(tri.max(axis=0)).astype(int),size-1)
        xx,yy=np.meshgrid(np.arange(left,right+1),np.arange(top,bottom+1))
        signs=[]
        for a,b in zip(tri,np.roll(tri,-1,axis=0)):
            signs.append((xx-a[0])*(b[1]-a[1])-(yy-a[1])*(b[0]-a[0]))
        mask=(np.min(signs,axis=0)>=0)|(np.max(signs,axis=0)<=0)
        rgb=[int(color[i:i+2],16) for i in (1,3,5)]
        pixels[top:bottom+1,left:right+1][mask]=rgb
    def chunk(kind,data):
        return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data))
    raw=b''.join(b'\x00'+row.tobytes() for row in pixels)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',*size,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
    (ROOT/'preview.png').write_bytes(png)
    (ROOT/"validation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__ == "__main__":
    main()
