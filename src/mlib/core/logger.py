import gettext
import logging
import os
import re
import sys
from datetime import datetime
from enum import Enum, IntEnum
from functools import wraps
from logging import Formatter, StreamHandler
from typing import Optional

import numpy as np
# import wx

from mlib.core.exception import MLibException


class LoggingMode(IntEnum):
    # 翻訳モード
    # 読み取り専用：翻訳リストにない文字列は入力文字列をそのまま出力する
    MODE_READONLY = 0
    # 更新あり：翻訳リストにない文字列は出力する
    MODE_UPDATE = 1


class LoggingLevel(Enum):
    DEBUG_FULL = 2
    TEST = 5
    TIMER = 12
    FULL = 15
    INFO_DEBUG = 22
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


def log_yield(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        v = f(*args, **kwargs)
        # try:
        #     if wx.GetApp():
        #         wx.YieldIfNeeded()
        # finally:
        #     pass
        return v

    return wrapper


class MLogger:
    class Decoration(Enum):
        IN_BOX = "in_box"
        BOX = "box"
        LINE = "line"

    DEFAULT_FORMAT = "%(message)s"
    STREAM_FORMAT = (
        "%(message)s [%(module)s:%(funcName)s][P-%(processName)s](%(asctime)s)"
    )
    FILE_FORMAT = "%(message)s [%(call_file)s:%(call_func)s:%(call_lno)s][P-%(processName)s](%(asctime)s)"

    # システム全体のロギングレベル
    total_level = logging.INFO
    # システム全体の開始出力日時
    output_datetime = ""

    # LoggingMode
    mode = LoggingMode.MODE_READONLY
    # デフォルトログファイルパス
    default_out_path = ""
    # デフォルト翻訳言語
    lang = "en"
    translator = None
    # i18n配置ディレクトリ
    lang_dir = None
    # セーブモード
    saving = True
    # ログ出力モード
    is_out_log = False
    # バージョン番号
    version_name = ""

    re_break = re.compile(r"\n")

    def __init__(
        self,
        module_name: str,
        level=logging.INFO,
    ):
        self.file_name = module_name
        self.default_level = level

        # ロガー
        self.logger = logging.getLogger("mutool").getChild(self.file_name)

        self.stream_err_handler = StreamHandler(sys.stderr)
        self.stream_err_handler.setFormatter(Formatter(self.STREAM_FORMAT))

        self.logger.setLevel(level)

    def get_extra(self, msg: str, func: Optional[str] = "", lno: Optional[int] = 0):
        return {
            "original_msg": msg,
            "call_file": self.file_name,
            "call_func": func,
            "call_lno": str(lno),
        }

    @log_yield
    def test(
        self,
        msg: str,
        *args,
        decoration: Optional[Decoration] = None,
        func: Optional[str] = "",
        lno: Optional[int] = 0,
        **kwargs,
    ):
        if self.default_level == 1:
            add_mlogger_handler(self)
            self.logger.info(
                self.create_message(msg, logging.DEBUG, None, decoration, **kwargs),
                extra=self.get_extra(msg, func, lno),
            )

    @log_yield
    def debug(
        self,
        msg: str,
        *args,
        decoration: Optional[Decoration] = None,
        func: Optional[str] = "",
        lno: Optional[int] = 0,
        **kwargs,
    ):
        if self.total_level <= logging.DEBUG and self.default_level <= self.total_level:
            add_mlogger_handler(self)
            self.logger.info(
                self.create_message(msg, logging.DEBUG, None, decoration, **kwargs),
                extra=self.get_extra(msg, func, lno),
            )

    @log_yield
    def info(
        self,
        msg: str,
        *args,
        title: Optional[str] = None,
        decoration: Optional[Decoration] = None,
        func: Optional[str] = "",
        lno: Optional[int] = 0,
        **kwargs,
    ):
        add_mlogger_handler(self)
        self.logger.info(
            self.create_message(msg, logging.INFO, title, decoration, **kwargs),
            extra=self.get_extra(msg, func, lno),
        )

    # ログレベルカウント
    @log_yield
    def count(
        self,
        msg: str,
        index: int,
        total_index_count: int,
        display_block: float,
        *args,
        title: Optional[str] = None,
        decoration: Optional[Decoration] = None,
        func: Optional[str] = "",
        lno: Optional[int] = 0,
        **kwargs,
    ):
        if 0 < total_index_count and (
            0 == index % display_block or index == total_index_count
        ):
            add_mlogger_handler(self)

            percentage = (index / total_index_count) * 100
            log_msg = "-- " + self.get_text(msg) + " [{i} ({p:.2f}%)]"
            count_msg = self.create_message(
                log_msg,
                logging.INFO,
                title,
                decoration,
                p=percentage,
                i=index,
                **kwargs,
            )

            self.logger.info(
                count_msg,
                extra=self.get_extra(count_msg, func, lno),
            )

    @log_yield
    def warning(
        self,
        msg: str,
        *args,
        title: Optional[str] = None,
        decoration: Optional[Decoration] = None,
        func: Optional[str] = "",
        lno: Optional[int] = 0,
        **kwargs,
    ):
        add_mlogger_handler(self)
        self.logger.warning(
            self.create_message(msg, logging.WARNING, title, decoration, **kwargs),
            extra=self.get_extra(msg, func, lno),
        )

    @log_yield
    def error(
        self,
        msg: str,
        *args,
        title: Optional[str] = None,
        decoration: Optional[Decoration] = None,
        func: Optional[str] = "",
        lno: Optional[int] = 0,
        **kwargs,
    ):
        add_mlogger_handler(self)
        self.logger.error(
            self.create_message(msg, logging.ERROR, title, decoration, **kwargs),
            extra=self.get_extra(msg, func, lno),
        )

    @log_yield
    def critical(
        self,
        msg: str,
        *args,
        title: Optional[str] = None,
        decoration: Optional[Decoration] = None,
        func: Optional[str] = "",
        lno: Optional[int] = 0,
        **kwargs,
    ):
        add_mlogger_handler(self)
        self.logger.critical(
            self.create_message(
                msg,
                logging.CRITICAL,
                title,
                decoration or MLogger.Decoration.BOX,
                **kwargs,
            ),
            exc_info=True,
            stack_info=True,
            extra=self.get_extra(msg, func, lno),
        )

    def quit(self):
        # 終了ログ
        with open("../log/quit.log", "w") as f:
            f.write("quit")

    def get_text(self, text: str, **kwargs) -> str:
        """指定された文字列の翻訳結果を取得する"""
        if not self.translator:
            if kwargs:
                return text.format(**kwargs)
            return text

        # 翻訳する
        if self.mode == LoggingMode.MODE_UPDATE:
            # 更新ありの場合、既存データのチェックを行って追記する
            messages = []
            with open(f"{self.lang_dir}/messages.pot", mode="r", encoding="utf-8") as f:
                messages = f.readlines()

            new_msg = self.re_break.sub("\\\\n", text)
            added_msg_idxs = [
                n + 1
                for n, inmsg in enumerate(messages)
                if "msgid" in inmsg and new_msg in inmsg
            ]

            if not added_msg_idxs:
                messages.append(f'\nmsgid "{new_msg}"\n')
                messages.append('msgstr ""\n')
                messages.append("\n")
                self.logger.debug("add message: %s", new_msg)

                with open(
                    f"{self.lang_dir}/messages.pot", mode="w", encoding="utf-8"
                ) as f:
                    f.writelines(messages)

        # 翻訳結果を取得する
        trans_text = self.translator.gettext(text)
        if kwargs:
            return str(trans_text.format(**kwargs))
        return trans_text

    # 実際に出力する実態
    def create_message(
        self,
        msg: str,
        level: int,
        title: Optional[str] = None,
        decoration: Optional["MLogger.Decoration"] = None,
        **kwargs,
    ) -> str:
        # 翻訳結果を取得する
        if logging.DEBUG < level:
            trans_msg = self.get_text(msg, **kwargs)
        else:
            # デバッグメッセージはそのまま変換だけ
            trans_msg = str(msg.format(**kwargs)) if kwargs else msg

        if decoration:
            if decoration == MLogger.Decoration.BOX:
                output_msg = self.create_box_message(trans_msg, level, title)
            elif decoration == MLogger.Decoration.LINE:
                output_msg = self.create_line_message(trans_msg, level, title)
            elif decoration == MLogger.Decoration.IN_BOX:
                output_msg = self.create_in_box_message(trans_msg, level, title)
            else:
                output_msg = trans_msg
        else:
            output_msg = trans_msg

        return output_msg

    def create_box_message(self, msg, level, title=None) -> str:
        msg_block = []
        msg_block.append("■■■■■■■■■■■■■■■■■")

        if level == logging.CRITICAL:
            msg_block.append("■　** CRITICAL **  ")

        elif level == logging.ERROR:
            msg_block.append("■　** ERROR **  ")

        elif level == logging.WARNING:
            msg_block.append("■　** WARNING **  ")

        elif logging.INFO >= level and title:
            msg_block.append(f"■　** {title} **  ")

        msg_block.extend([f"■　{msg_line}" for msg_line in msg.split("\n")])
        msg_block.append("■■■■■■■■■■■■■■■■■")

        return "\n".join(msg_block)

    def create_line_message(self, msg, level, title=None) -> str:
        msg_block = [
            f"■ {msg_line} --------------------" for msg_line in msg.split("\n")
        ]
        return "\n".join(msg_block)

    def create_in_box_message(self, msg, level, title=None) -> str:
        msg_block = [f"■　{msg_line}" for msg_line in msg.split("\n")]
        return "\n".join(msg_block)

    @classmethod
    def initialize(
        cls,
        lang: str,
        root_dir: str,
        version_name: str,
        mode: LoggingMode = LoggingMode.MODE_READONLY,
        saving: bool = True,
        level=logging.INFO,
        is_out_log: bool = False,
    ):
        logging.basicConfig(level=level, format=cls.STREAM_FORMAT)
        cls.total_level = level
        cls.mode = LoggingMode.MODE_READONLY if lang != "ja" else mode
        cls.lang = lang
        cls.saving = saving
        cls.is_out_log = is_out_log
        cls.lang_dir = f"{root_dir}/i18n"
        cls.version_name = version_name

        # 翻訳用クラスの設定
        cls.translator = gettext.translation(
            "messages",  # domain: 辞書ファイルの名前
            localedir=f"{root_dir}/i18n",  # 辞書ファイル配置ディレクトリ
            languages=[lang],  # 翻訳に使用する言語
            fallback=True,  # .moファイルが見つからなかった時は未翻訳の文字列を出力
        )

        output_datetime = "{0:%Y%m%d_%H%M%S}".format(datetime.now())
        cls.output_datetime = output_datetime

        # ファイル出力ありの場合、ログファイル名生成
        if is_out_log:
            cls.default_out_path = f"{root_dir}/mutool_{output_datetime}.log"

        if os.path.exists(f"{root_dir}/quit.log"):
            # 終了ログは初期化時に削除
            os.remove(f"{root_dir}/quit.log")


def add_mlogger_handler(logger: MLogger) -> None:
    for h in logger.logger.handlers:
        logger.logger.removeHandler(h)

    logger.stream_err_handler = StreamHandler(sys.stderr)
    logger.stream_err_handler.setFormatter(Formatter(logger.STREAM_FORMAT))
    logger.logger.addHandler(logger.stream_err_handler)


def parse2str(obj: object) -> str:
    """オブジェクトの変数の名前と値の一覧を文字列で返す

    Parameters
    ----------
    obj : object

    Returns
    -------
    str
        変数リスト文字列
        Sample[x=2, a=sss, child=ChildSample[y=4.5, b=xyz]]
    """
    return f"{obj.__class__.__name__}[{', '.join([f'{k}={round_str(v)}' for k, v in vars(obj).items()])}]"


def round_str(v: object, decimals=5) -> str:
    """
    丸め処理付き文字列変換処理

    小数だったら丸めて一定桁数までしか出力しない
    """
    if isinstance(v, float):
        return f"{round(v, decimals)}"
    elif isinstance(v, np.ndarray):
        return f"{np.round(v, decimals)}"
    elif hasattr(v, "data"):
        return f"{np.round(v.__getattribute__('data'), decimals)}"
    else:
        return f"{v}"


# ファイルのエンコードを取得する
def get_file_encoding(file_path):
    try:
        f = open(file_path, "rb")
        fbytes = f.read()
        f.close()
    except Exception:
        raise MLibException("unknown encoding!")

    codes = ("utf-8", "shift-jis")

    for encoding in codes:
        try:
            fstr = fbytes.decode(encoding)  # bytes文字列から指定文字コードの文字列に変換
            fbytes = fstr.encode("utf-8")  # uft-8文字列に変換
            # 問題なく変換できたらエンコードを返す
            return encoding
        except Exception as e:
            print(e)
            pass

    raise MLibException("unknown encoding!")
