from qma_face.app import main

if __name__ == "__main__":
    try:
        status = main()
    except Exception:
        import traceback

        from qma_face.core.config import data_directory

        target = data_directory()
        target.mkdir(parents=True, exist_ok=True)
        (target / "startup-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        status = 1
    raise SystemExit(status)
