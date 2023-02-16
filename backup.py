import time
import logging
import threading

from pathlib import Path
from sqlite3 import Connection
from qbittorrentapi import Client

from global_var import TORRENTS_PATH, RAW_PATH
from sqlite import get_connect, update, select, insert
from qbittorrent import get_qbt_client, get_complete_list, download_from_file, delete_torrent
from utils import zipfile, backup2gd, remove

MAX_DOWNLOAD_TASK = 500


def deal_download_file(conn: Connection, qbt_client: Client):
    while True:
        try:
            deal_list = get_complete_list(qbt_client)
            for data in deal_list:

                # 记录到数据库
                path = Path(data['path'])
                assert path.exists(), 'file no exist.'
                insert(conn, **data)

                # 压缩文件
                uid = data['uid']
                where = [('uid', uid)]
                zip_path = zipfile(path, uid)
                update(conn, where=where, state=2)

                # 删除源文件
                remove(path)
                delete_torrent(qbt_client, hash=data['hash'])

                # 备份到gd
                if backup2gd(zip_path, data['type']):
                    update(conn, where=where, state=3)
            time.sleep(60)
        except Exception as e:
            logging.error(f'deal file error {e.args}')


def download_from_lemon(conn: Connection, qbt_client: Client):
    download_list = select(conn, ['uid'], [('state', 0)])
    while download_list:
        try:
            while len(qbt_client.torrents_info()) > MAX_DOWNLOAD_TASK:
                time.sleep(60)
            for uid in download_list:
                file = TORRENTS_PATH / f'{uid}.torrent'
                download_from_file(qbt_client, file, RAW_PATH / 'uid')
            download_list = select(conn, ['uid'], [('state', 0)])
        except Exception as e:
            logging.error(f'download file error {e.args}')


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO, filename='backup.log')
    conn = get_connect()
    qbt_client = get_qbt_client()
    assert qbt_client, 'qbittorrent connect fail'

    deal_thread = threading.Thread(target=deal_download_file, args=(conn, qbt_client), daemon=True)
    deal_thread.start()
    deal_thread.join()

    # download_thread = threading.Thread(target=download_from_lemon, args=(conn, qbt_client), daemon=True)
    # download_thread.start()
    # download_thread.join()
