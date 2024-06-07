# 获取虎牙直播的真实流媒体地址。
import json
import requests
import re
import base64
import hashlib
from urllib.parse import parse_qs, urlencode, unquote
from datetime import datetime
import random
import time
import traceback


class HuYa:
    def __init__(self, room_id: str):
        self.room_id = room_id

    def get_anonymous_uid(self):
        data = {
            "appId": 5002,
            "byPass": 3,
            "context": "",
            "version": "2.4",
            "data": {}
        }
        url = "https://udblgn.huya.com/web/anonymousLogin"
        try:
            resp = requests.post(url, json=data, timeout=5)
            resp.raise_for_status()
            return resp.json()["data"]["uid"]
        except requests.RequestException as e:
            raise ConnectionError(f"获取匿名UID失败: {e}")

    @staticmethod
    def get_uuid():
        now = datetime.now().timestamp() * 1000
        rand = random.randint(0, 1000) | 0
        return int((now % 10000000000 * 1000 + rand) % 4294967295)

    def process_anticode(self, anticode, uid, streamname):
        url_query = dict(parse_qs(anticode))
        platform_id = 102  # web = 100, mobile = 103
        url_query['ctype'][0] = 'tars_mp'
        uid = int(uid)
        convert_uid = (uid << 8 | uid >> (32 - 8)) & 0xFFFFFFFF
        ws_time = url_query['wsTime'][0]
        seq_id = uid + int(time.time() * 1000)
        ws_secret_prefix = base64.b64decode(unquote(url_query['fm'][0]).encode()).decode().split('_')[0]
        ws_secret_hash = hashlib.md5(f"{seq_id}|{url_query['ctype'][0]}|{platform_id}".encode()).hexdigest()
        ws_secret = hashlib.md5(f'{ws_secret_prefix}_{convert_uid}_{streamname}_{ws_secret_hash}_{ws_time}'.encode()).hexdigest()

        query_dict = {
            "ctype": url_query['ctype'][0],
            "fs": url_query['fs'][0],
            "sv": 2401090219,
            "ver": 1,
            "seqid": seq_id,
            "uid": convert_uid,
            "uuid": self.get_uuid(),
            "wsSecret": ws_secret,
            "wsTime": ws_time,
            "t": platform_id,
            # -- Attributes below are optional
            "sdk_sid": int(time.time() * 1000),
            "codec": "264",
            "sphdDC": "huya",
            "exsphd": url_query['exsphd'][0],
            "sphd": url_query['sphd'][0],
            "sphdcdn": url_query['sphdcdn'][0],
        }

        return urlencode(query_dict)

    def get_stream_info(self, info):
        stream_info = dict({'flv': {}, 'hls': {}})
        cdn_map = dict({'AL': '阿里', 'TX': '腾讯', 'HW': '华为', 'HS': '火山', 'WS': '网宿', 'HY': '虎牙'})
        uid = self.get_anonymous_uid()

        streams = info.get("roomInfo", {}).get("tLiveInfo", {}).get("tLiveStreamInfo", {}).get("vStreamInfo", {}).get("value", [])
        for s in streams:
            cdn_type = cdn_map.get(s["sCdnType"], s["sCdnType"])
            if s["sFlvUrl"]:
                url = s["sFlvUrl"].replace('http://', 'https://')
                stream_info["flv"][cdn_type] = "{}/{}.{}?{}".format(
                    url, s["sStreamName"], s["sFlvUrlSuffix"], self.process_anticode(s["sFlvAntiCode"], uid, s["sStreamName"])
                )
            if s["sHlsUrl"]:
                url = s["sHlsUrl"].replace('http://', 'https://')
                stream_info["hls"][cdn_type] = "{}/{}.{}?{}".format(
                    url, s["sStreamName"], s["sHlsUrlSuffix"], self.process_anticode(s["sHlsAntiCode"], uid, s["sStreamName"]))
        return stream_info

    def get_real_url(self):
        room_url = 'https://m.huya.com/' + str(self.room_id)
        header = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 
                'Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/75.0.3770.100 Mobile Safari/537.36 '
        }
        try:
            response = requests.get(url=room_url, headers=header, timeout=10).text
            match = re.search(r'\s*<script>\s*window.HNF_GLOBAL_INIT\s*=\s*(\{.*?\})\s*</script>', response, re.DOTALL)
            if not match:
                return {"errors": "虎牙响应格式已更改"}

            room_info_str = match.group(1)
            # Remove js functions
            room_info_str = re.sub(r'function\s*\([^{]*\{[^}]*\}', '""', room_info_str)
            room_info = json.loads(room_info_str)
            if "roomInfo" not in room_info:
                return {"errors": f"直播间（{self.room_id}）不存在"}

            live_status = room_info["roomInfo"].get("eLiveStatus")
            if live_status == 2:
                return self.get_stream_info(room_info)
            elif live_status == 3:
                print('该直播间正在回放历史直播，低清晰度源地址为：')
                return "https:{}".format(base64.b64decode(room_info["roomProfile"]["liveLineUrl"]).decode('utf-8'))
            else:
                return {"errors": f"直播间（{self.room_id}）未开播"}
        except requests.RequestException as e:
            return {"errors": f"获取虎牙real url时出错: {e}"}
        except Exception:
            return {"errors": f"处理响应时出错: {traceback.format_exc()}"}


if __name__ == '__main__':
    room_id = input('输入虎牙直播房间号：\n')
    huya = HuYa(room_id)
    real_url = huya.get_real_url()
    print('该直播间源地址为：')
    print(json.dumps(real_url, ensure_ascii=False))
