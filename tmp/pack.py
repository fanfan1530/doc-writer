import tarfile, os, glob

OUT = r"C:\Users\Lenovo\Desktop\2026正式期末作品"
os.makedirs(OUT, exist_ok=True)

# Archive 1: app source
src = r"C:\Users\Lenovo\doc-writer\tmp\pkg\app"
out1 = os.path.join(OUT, "app-source.tar.gz")
with tarfile.open(out1, "w:gz") as tar:
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".pyc"):
                continue
            full = os.path.join(root, f)
            arcname = os.path.relpath(full, src).replace("\\", "/")
            tar.add(full, arcname=arcname)
size1 = os.path.getsize(out1) / 1024 / 1024
print(f"app-source.tar.gz: {size1:.2f} MB")

# Archive 2: frontend dist
src2 = r"C:\Users\Lenovo\doc-writer\frontend\dist"
out2 = os.path.join(OUT, "frontend-dist.tar.gz")
with tarfile.open(out2, "w:gz") as tar:
    for root, dirs, files in os.walk(src2):
        for f in files:
            full = os.path.join(root, f)
            arcname = os.path.relpath(full, src2).replace("\\", "/")
            tar.add(full, arcname=arcname)
size2 = os.path.getsize(out2) / 1024 / 1024
print(f"frontend-dist.tar.gz: {size2:.2f} MB")

# Archive 3: split wheels into <9MB parts
wheels_dir = r"C:\Users\Lenovo\doc-writer\tmp\wheels"
wheel_files = sorted(glob.glob(os.path.join(wheels_dir, "*.whl")))

# Create a single tar of all wheels, then split
wheels_tar = os.path.join(r"C:\Users\Lenovo\doc-writer\tmp", "wheels.tar")
with tarfile.open(wheels_tar, "w") as tar:
    for wf in wheel_files:
        tar.add(wf, arcname=os.path.basename(wf))

# gzip the tar
import gzip, shutil
wheels_gz = wheels_tar + ".gz"
with open(wheels_tar, "rb") as f_in:
    with gzip.open(wheels_gz, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
os.remove(wheels_tar)

total_size = os.path.getsize(wheels_gz) / 1024 / 1024
print(f"wheels.tar.gz: {total_size:.2f} MB")

# Split into 9MB chunks
chunk_size = 9 * 1024 * 1024
with open(wheels_gz, "rb") as f:
    part_num = 0
    while True:
        chunk = f.read(chunk_size)
        if not chunk:
            break
        part_name = os.path.join(OUT, f"wheels.tar.gz.part-{part_num:02d}")
        with open(part_name, "wb") as pf:
            pf.write(chunk)
        part_mb = os.path.getsize(part_name) / 1024 / 1024
        print(f"  {os.path.basename(part_name)}: {part_mb:.2f} MB")
        part_num += 1

os.remove(wheels_gz)
print(f"\nTotal wheels parts: {part_num}")
print(f"\nAll packages in: {OUT}")
for f in sorted(os.listdir(OUT)):
    sz = os.path.getsize(os.path.join(OUT, f)) / 1024 / 1024
    print(f"  {f}: {sz:.2f} MB")
