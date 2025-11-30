from processor import process_one
import time


def main():
    """
    Detector daemon loop.
    Runs as fast as possible, no artificial sleeps.
    """

    while True:
        try:
            processed = process_one()
            print(processed)

            if not processed.get("status"):
                time.sleep(5)

        except Exception as e:
            print(e)
            time.sleep(10)

if __name__ == "__main__":
    main()
