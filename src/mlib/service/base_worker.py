import os
from functools import wraps
from threading import Thread, current_thread, enumerate
from time import sleep, time
from typing import Any, Callable, Optional

# import wx

from mlib.core.exception import MKilledException, MLibException
from mlib.core.logger import MLogger
# from mlib.service.form.notebook_panel import NotebookPanel

logger = MLogger(os.path.basename(__file__))
__ = logger.get_text


# https://doloopwhile.hatenablog.com/entry/20090627/1275175850
class SimpleThread(Thread):
    """呼び出し可能オブジェクト（関数など）を実行するだけのスレッド"""

    def __init__(self, base_thread, callable) -> None:
        self.base_thread = base_thread
        self.callable = callable
        self._result = None
        self.killed = False
        super(SimpleThread, self).__init__(name="simple_thread")

    def run(self) -> None:
        self._result = self.callable(self.base_thread)

    def result(self) -> Any:
        return self._result


def verify_thread(callable: Callable):
    """スレッドの生死を確認するデコレーター"""

    @wraps(callable)
    def f(self, *args, **kwargs):
        thread = current_thread()
        if (isinstance(thread, SimpleThread) and thread.killed) or thread._kwargs.get(
            "killed"
        ):  # type: ignore
            raise MKilledException

        return callable(self, *args, **kwargs)

    return f


def task_takes_time(callable: Callable):
    """
    callable本来の処理は別スレッドで実行しながら、
    ウィンドウを更新するwx.YieldIfNeededを呼び出し続けるようにする
    """

    @wraps(callable)
    def f(worker: "BaseWorker"):
        thread = SimpleThread(worker, callable)
        thread.daemon = True
        thread.start()
        while thread.is_alive():
            # wx.YieldIfNeeded()
            sleep(0.01)

            if worker.killed:
                # 呼び出し元から停止命令が出ている場合、自分以外の全部のスレッドに終了命令
                for th in enumerate():
                    if th.ident != current_thread().ident:
                        if isinstance(th, SimpleThread):
                            th.killed = True
                        else:
                            th._kwargs["killed"] = True  # type: ignore
                break

        return thread.result()

    return f


def show_worked_time(elapsed_time: float):
    """経過秒数を時分秒に変換"""
    td_m, td_s = divmod(elapsed_time, 60)
    td_h, td_m = divmod(td_m, 60)

    if td_m == 0:
        worked_time = "00:00:{0:02d}".format(int(td_s))
    elif td_h == 0:
        worked_time = "00:{0:02d}:{1:02d}".format(int(td_m), int(td_s))
    else:
        worked_time = "{0:02d}:{1:02d}:{2:02d}".format(int(td_h), int(td_m), int(td_s))

    return worked_time


class BaseWorker:
    def __init__(self, panel, result_func: Callable) -> None:
        self.start_time = 0.0
        self.panel = panel
        self.frame = panel.frame
        self.started = False
        self.killed = False
        self.result: bool = True
        self.result_data: Optional[Any] = None
        self.result_func = result_func
        self.max_worker = (
            1
            if self.frame.is_saving
            else max(1, int(min(32, (os.cpu_count() or 0) + 4) / 2))
        )

    def start(self) -> None:
        self.started = True
        self.start_time = time()

        self.run()

        if not self.killed:
            self.started = False
            self.killed = False
            self.result_func(
                result=self.result,
                data=self.result_data,
                elapsed_time=show_worked_time(time() - self.start_time),
            )

    def stop(self) -> None:
        self.killed = True

    @task_takes_time
    def run(self) -> None:
        try:
            self.thread_execute()
            self.result = True
        except MKilledException as e:
            logger.info(e.message, title="STOP", decoration=MLogger.Decoration.BOX)
            self.result = False
        except MLibException as e:
            logger.error(
                "[{v}]\n処理が継続できないため、中断しました\n----------------\n{m}",
                v=logger.version_name,
                m=e.message,
                decoration=MLogger.Decoration.BOX,
                **e.kwargs,
            )
            self.result = False
        except Exception:
            logger.critical("[{v}]\n予期せぬエラーが発生しました", v=logger.version_name)
            self.result = False
        finally:
            try:
                if logger.is_out_log or (not self.result and not self.killed):
                    # ログ出力
                    self.output_log()
            except Exception:
                pass
            self.started = False
            self.killed = False

    def thread_execute(self) -> None:
        raise NotImplementedError

    def output_log(self) -> None:
        raise NotImplementedError
