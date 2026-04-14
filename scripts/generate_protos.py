import ast
import shutil
import subprocess
from pathlib import Path

from grpc_tools import protoc


def main():
    workdir = Path.cwd()

    # Get script directory and project root
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    protobufs_dir = project_root / "protobufs"
    generated_dir = protobufs_dir / "generated"
    generated_dir.mkdir(exist_ok=True)

    target_dir = project_root / "aiosteampy" / "webapi" / "protobufs"
    target_dir.mkdir(exist_ok=True)
    (target_dir / "__init__.py").touch(exist_ok=True)

    # Find all .proto files
    proto_files = sorted(protobufs_dir.glob("*.proto"))
    if not proto_files:
        raise FileNotFoundError(f"No .proto files found in {protobufs_dir}")

    # Prepare arguments with relative paths due to protoc dumbness
    base_args = [
        f"-I {protobufs_dir.relative_to(workdir)}",
        "--python_betterproto2_opt=client_generation=none",
    ]

    for source_file in proto_files:
        # Run protoc
        file_generated_dir = generated_dir / source_file.stem
        file_generated_dir.mkdir(exist_ok=True)
        args = base_args + [
            f"--python_betterproto2_out={file_generated_dir.relative_to(workdir)}",
            str(source_file.relative_to(workdir)),
        ]
        protoc.main(args)

        # Process generated __init__.py
        init_file = file_generated_dir / "__init__.py"
        assert init_file.exists()
        # Remove message pool statements as excessive
        content = init_file.read_text(encoding="utf-8")
        tree = ast.parse(content)

        # Find comment
        comment = ""
        for line in content.splitlines(keepends=True):
            if line.startswith("#"):
                comment += line
            else:
                break

        comment += "\n# Processed by generate_protos.py: removed 'message_pool', formatted.\n"

        # Filter out statements containing 'message_pool'
        new_body = []
        for node in tree.body:
            segment = ast.get_source_segment(content, node)
            if segment and "message_pool" not in segment:
                new_body.append(node)

        # Create a new module with the filtered body
        new_tree = ast.Module(body=new_body, type_ignores=[])

        # Unparse back to source and write to target file
        new_content = comment + "\n" + ast.unparse(new_tree)

        target_file = (target_dir / source_file.stem).with_suffix(".py")
        target_file.write_text(new_content, encoding="utf-8")

    # Format with ruff, optimize imports
    subprocess.run(["ruff", "format", str(target_dir)], check=True, cwd=project_root)
    subprocess.run(["ruff", "check", "--select", "I", "--fix", str(target_dir)], check=True, cwd=project_root)

    # Remove generated directory
    shutil.rmtree(generated_dir)


if __name__ == "__main__":
    main()
