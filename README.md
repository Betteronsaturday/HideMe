# HideMe 🫥

HideMe anonymizes personal information in text, PDFs, and images on your own computer. The document never leaves the machine, and the page shows only placeholders. The map from each placeholder back to the original value stays in a local file and is not returned by the API.

The server listens only on `127.0.0.1:5006`. It does not use API keys.

## What it hides

| Placeholder | What it removes |
|---|---|
| `[USERNAME_1]` | username, login, nickname |
| `[SALARY_1]` | salary, wage, stipend, Gehalt, salaire, sueldo |
| `[CURRENCY_1]` | amounts in other currencies |
| `[JOBTITLE_1]` | job title |
| `[EMAIL_1]` | email address |
| `[SOCIAL_1]` | social profiles and @handles |
| `[PHONE_1]` | phone numbers, including international formats |
| `[ADDRESS_1]` | street addresses (via, street, rue, Straße, calle) |
| `[PHOTO_1]` | images in the text, inside a PDF, or a whole image file |

A text file is read by its contents, whatever the extension is. If the bytes are an image or a PDF, they are handled as that format. An image is replaced as a whole. Text drawn inside a picture is not read.

Each category is one check in `hideme/detectors.py`. A check scans the whole text. A new category is another check in that file.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m hideme --host 127.0.0.1 --port 5006
```

Open [http://127.0.0.1:5006](http://127.0.0.1:5006). Paste text or choose a file.

Sessions are stored in `~/.local/share/hideme/sessions/`.

## Cursor

`mcp/server.py` is a local MCP server with two tools: anonymize a file, and restore a session only when you ask. After a change, reload the window (`Cmd+Shift+P` → **Developer: Reload Window**).

## License

MIT. See [LICENSE](LICENSE).
