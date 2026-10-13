"""保有銘柄など個人の情報を、公開リポジトリに平文で置かないための暗号化。
- 保有銘柄はGitHubのSecret「HOLDINGS」（JSON：{"コード": ["銘柄名", 株数], ...}）から読む
- 結果は data/private.enc に AES-256-GCM で暗号化して保存（鍵はSecret「DASH_PASS」から PBKDF2 で生成）
- ダッシュボードはスマホ側でパスフレーズを入力して復号する（ブラウザ標準のWebCrypto）"""
import base64
import json
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITER = 310_000


def holdings():
    raw = os.environ.get("HOLDINGS", "").strip()
    if not raw:
        return {}
    try:
        return {str(k): (v[0], float(v[1])) for k, v in json.loads(raw).items()}
    except Exception as e:
        print("HOLDINGSの形式が不正", e)
        return {}


def encrypt(obj, path="data/private.enc"):
    pw = os.environ.get("DASH_PASS", "")
    if not pw:
        print("DASH_PASS未設定のため個人データは保存しない")
        return False
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pw.encode())
    ct = AESGCM(key).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode(), None)
    open(path, "w").write(base64.b64encode(salt + iv + ct).decode())
    return True
