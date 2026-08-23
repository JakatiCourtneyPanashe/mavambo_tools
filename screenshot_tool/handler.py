import json
import pathlib
import sys


def fail(message):
    json.dump({"error": message}, sys.stdout)
    raise SystemExit(0)


def inside_project(root, name):
    p = pathlib.Path(name)
    if p.is_absolute() or ".." in p.parts:
        return None
    target = (root / p).resolve()
    return target if target == root or root in target.parents else None


def main():
    try:
        env = json.load(sys.stdin)
        args = env.get("arguments") or {}
        root = pathlib.Path(env["cwd"]).resolve()

        filename = args.get("filename", "screenshot.png")
        filename_path = pathlib.Path(filename)

        if filename_path.is_absolute() or ".." in filename_path.parts:
            fail("Refused filename: use only a simple filename or relative filename.")

        if filename_path.suffix.lower() != ".png":
            fail("The output filename must use the .png extension.")

        # Fixed Windows destination requested by the user.
        target = pathlib.Path(
            r"C:\Users\sparr\Desktop\MAVAMBO_COMBINED\coding_agent\workspace_root\man"
        ) / filename_path

        # A region is only used when all four coordinates are supplied.
        region_keys = ("left", "top", "width", "height")
        supplied = [k in args for k in region_keys]
        if any(supplied) and not all(supplied):
            fail("For a region capture, provide left, top, width, and height together.")

        try:
            import mss
            from PIL import Image
        except ImportError:
            fail("Screenshot dependencies are unavailable. Install the declared tool dependencies.")

        target.parent.mkdir(parents=True, exist_ok=True)

        with mss.mss() as sct:
            if all(supplied):
                monitor = {
                    "left": args["left"],
                    "top": args["top"],
                    "width": args["width"],
                    "height": args["height"],
                }
            else:
                # mss monitor 0 is the virtual bounding box of all monitors.
                monitor = sct.monitors[0]

            shot = sct.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
            image.save(target, format="PNG")

        json.dump({
            "result": {
                "path": str(target.relative_to(root)),
                "width": image.width,
                "height": image.height,
                "format": "PNG"
            }
        }, sys.stdout)

    except Exception as exc:
        fail(f"Screenshot failed: {exc}")


if __name__ == "__main__":
    main()
