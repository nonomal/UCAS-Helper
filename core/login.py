# -*- coding: utf-8 -*-
"""
-----------------Init-----------------------
            Name: login.py
            Description:
            Author: GentleCP
            Email: 574881148@qq.com
            WebSite: https://www.gentlecp.com
            Date: 2020-08-31 
-------------Change Logs--------------------


--------------------------------------------
"""
import base64
import re
import requests
import settings
import warnings
from PIL import Image
from io import BytesIO
from bs4 import BeautifulSoup

import configparser
from handler.logger import LogHandler
from handler.exception import ExitStatus
from util.functions import get_cfg
from util.ocr import do_ocr
from Crypto.Cipher import PKCS1_v1_5 as Cipher_pksc1_v1_5
from Crypto.PublicKey import RSA

warnings.filterwarnings('ignore')


def simulate_JSEncrypt(password, public_key):
    public_key = '-----BEGIN PUBLIC KEY-----\n' + public_key + '\n-----END PUBLIC KEY-----'
    rsakey = RSA.importKey(public_key)
    cipher = Cipher_pksc1_v1_5.new(rsakey)
    cipher_text = base64.b64encode(cipher.encrypt(password.encode()))
    return cipher_text.decode()


class Loginer(object):
    """
    登录课程网站
    """

    def __init__(self,
                 urls=None,
                 user_config_path='../conf/user_config.ini',
                 *args, **kwargs):
        '''
        :param urls:
        :param user_config_path:
        :param args:
        :param kwargs: 目前仍支持从settings中读取设备,后续考虑移除
        '''
        self._logger = LogHandler("Loginer")
        self._S = requests.session()
        self._user_config_path = user_config_path
        self._cfg = get_cfg(self._user_config_path)
        self._urls = urls

        self.headers = {
            'Connection': 'keep-alive',
            'sec-ch-ua': '"Google Chrome";v="87", "\\"Not;A\\\\Brand";v="99", "Chromium";v="87"',
            'Accept': '*/*',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua-mobile': '?0',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.67 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://onestop.ucas.ac.cn',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://onestop.ucas.ac.cn/',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

    def _set_user_info(self):
        '''
        set user info from conf/user_config.ini
        :return: None
        '''
        try:
            username = self._cfg.get('user_info', 'username')
            password = self._cfg.get('user_info', 'password')
            key = self._cfg.get('sep_info', 'key')
            password = simulate_JSEncrypt(password, key)
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            self._logger.error(
                'Can not read user information from {}, please enter your personal information at first.(do not store it in settings.py, it is no longer supported)'.format(
                    self._user_config_path))
            exit(ExitStatus.CONFIG_ERROR)
        else:
            if not username or not password:
                # 用户名或密码信息为空
                self._logger.error(
                    'User information can not be empty, check your user information in {}.'.format(
                        self._user_config_path))
                exit(ExitStatus.CONFIG_ERROR)

            else:
                self._user_info = {
                    'username': username,
                    'password': password,
                    'remember': 'undefined'
                }

    def __keep_session(self):
        try:
            res = self._S.get(url=self._urls['course_select_url']['http'], headers=self.headers, timeout=5)
        except requests.Timeout:
            res = self._S.get(url=self._urls['course_select_url']['https'], headers=self.headers)
        course_select_url = re.search(r"window.location.href='(?P<course_select_url>.*?)'", res.text).groupdict().get(
            "course_select_url")
        self._S.get(course_select_url, headers=self.headers)

    def login(self):
        self._set_user_info()
        # self._S.get(url=self._urls['home_url']['https'], headers=self.headers, verify=False)  # 获取identity
        try:
            res = self._S.get(url=self._urls['course_select_url']['http'], headers=self.headers, timeout=5)
        except requests.Timeout:
            res = self._S.get(url=self._urls['course_select_url']['https'], headers=self.headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        try:
            res = self._S.get(url=self._urls['bak_home_url']['http'] + soup.select_one("img#code").get("src"),
                              headers=self.headers)
        except:
            # 校园网内不需要验证码
            post_data = {
                'userName': self._user_info.get('username', ''),
                'pwd': self._user_info.get('password', ''),
                'sb': 'sb'
            }
        else:
            captcha_img = Image.open(BytesIO(res.content))
            # captcha_img.show()
            # captcha_code = input("请输入图片展示的验证码信息:")
            captcha_code = do_ocr(captcha_img)
            post_data = {
                'userName': self._user_info.get('username', ''),
                'pwd': self._user_info.get('password', ''),
                'certCode': captcha_code,
                'sb': 'sb'
            }
        try:
            res = self._S.post(url=self._urls["bak_login_url"]['http'], data=post_data, headers=self.headers,
                               timeout=10)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout):
            self._logger.error("网络连接失败，请确认你的网络环境后重试！")
            exit(ExitStatus.NETWORK_ERROR)
        if res.status_code != 200:
            self._logger.error('sep登录失败，未知错误，请到github提交issue，等待作者修复.')
            exit(ExitStatus.UNKNOW_ERROR)
        else:
            if "请输入您的密码" in res.text:
                self._logger.error("sep登录失败，请检查你的用户名和密码设置以及验证码输入是否正确！")
                exit(ExitStatus.CONFIG_ERROR)
            else:
                self._logger.info("sep登录成功！")
                self.__keep_session()


if __name__ == '__main__':
    loginer = Loginer(urls=settings.URLS,
                      user_config_path='../conf/user_config.ini')
    loginer.login()
