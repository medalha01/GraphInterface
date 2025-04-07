# Graphics Editor

A 2D graphics editor :)

## Setup

1.  **Create and activate a virtual environment:**
    ```bash
    # Ensure you have virtualenv installed (pip install virtualenv)
    virtualenv -p python3 venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

2.  **Install dependencies:**
    Create a `requirements.txt` file with the following content:
    ```txt
    PyQt5>=5.15
    numpy>=1.18
    Pillow>=8.0 # Optional: For creating dummy icons if real ones are missing
    ```
    Then run:
    ```bash
    pip install -r requirements.txt
    ```

## Run

Make sure you are in the directory *containing* the `graphics_editor` package folder. Then run the application using:

```bash
python -m graphics_editor
