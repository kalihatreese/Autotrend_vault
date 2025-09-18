import datetime

import requests


def get_products():
    try:
        with open("vault_ingest.txt") as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return ["Vault is empty"]


def post_to_gist(content):
    url = "https://api.github.com/gists"
    payload = {
        "description": "AutoTrend Ad",
        "public": True,
        "files": {"ad.txt": {"content": content}},
    }
    r = requests.post(url, json=payload)
    return r.json().get("html_url", "Gist failed")


def post_to_telegraph(content):
    r = requests.post(
        "https://telegra.ph/create", data={"title": "AutoTrend Ad", "content": content}
    )
    return r.url if r.ok else "Telegraph failed"


def post_to_pasteee(content):
    r = requests.post(
        "https://paste.ee/api", data={"description": "AutoTrend Ad", "paste": content}
    )
    return r.url if r.ok else "Paste.ee failed"


def fire_ad():
    products = get_products()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = f"🧬 AutoTrend Ad ({timestamp})\n\n" + "\n".join(products)

    urls = []
    urls.append(post_to_gist(content))
    urls.append(post_to_telegraph(content))
    urls.append(post_to_pasteee(content))

    with open("adbot_log.txt", "a") as f:
        for u in urls:
            f.write(f"[{timestamp}] {u}\n")


if __name__ == "__main__":
    fire_ad()
