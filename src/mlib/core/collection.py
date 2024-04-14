import hashlib
from bisect import bisect_left
from typing import Generic, Iterator, Optional, TypeVar, Union

from mlib.core.base import BaseModel, Encoding
from mlib.core.part import BaseIndexModel, BaseIndexNameModel
from mlib.service.base_worker import verify_thread

TBaseIndexModel = TypeVar("TBaseIndexModel", bound=BaseIndexModel)
TBaseIndexNameModel = TypeVar("TBaseIndexNameModel", bound=BaseIndexNameModel)


class BaseIndexDictModel(Generic[TBaseIndexModel], BaseModel):
    """BaseIndexModelのリスト基底クラス"""

    __slots__ = (
        "data",
        "indexes",
    )

    def __init__(self) -> None:
        """モデルリスト"""
        super().__init__()
        self.data: dict[int, TBaseIndexModel] = {}
        self.indexes: list[int] = []

    def create(self) -> "TBaseIndexModel":
        raise NotImplementedError

    def __getitem__(self, index: int) -> TBaseIndexModel:
        if 0 > index:
            # マイナス指定の場合、後ろからの順番に置き換える
            index = len(self.data) + index
            return self.data[self.indexes[index]]
        if index in self.data:
            return self.data[index]

        # なかったら追加
        self.append(self.create())
        return self.data[index]

    def range(
        self, start: int = 0, stop: int = -1, step: int = 1
    ) -> list[TBaseIndexModel]:
        if 0 > stop:
            # マイナス指定の場合、後ろからの順番に置き換える
            stop = len(self.data) + stop + 1
        return [self.data[self.indexes[n]] for n in range(start, stop, step)]

    def __setitem__(self, index: int, v: TBaseIndexModel) -> None:
        self.data[index] = v

    @verify_thread
    def append(self, value: TBaseIndexModel, is_sort: bool = False) -> None:
        if 0 > value.index:
            value.index = len(self.data)
        self.data[value.index] = value
        if is_sort:
            self.sort_indexes()
        else:
            self.indexes.append(value.index)

    @verify_thread
    def sort_indexes(self) -> None:
        self.indexes = sorted(self.data.keys()) if self.data else []

    def __delitem__(self, index: int) -> None:
        if index in self.data:
            del self.data[index]

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self) -> Iterator[TBaseIndexModel]:
        return iter([self.data[k] for k in sorted(self.data.keys())])

    def __contains__(self, key: int) -> bool:
        return key in self.data

    def __bool__(self) -> bool:
        return 0 < len(self.data)

    @property
    def last_index(self) -> int:
        return max(self.data.keys())


TBaseIndexDictModel = TypeVar("TBaseIndexDictModel", bound=BaseIndexDictModel)


class BaseIndexNameDictModel(Generic[TBaseIndexNameModel], BaseModel):
    """BaseIndexNameModelの辞書基底クラス"""

    __slots__ = (
        "name",
        "data",
        "cache",
        "indexes",
        "_names",
    )

    def __init__(self, name: str = "") -> None:
        """モデル辞書"""
        super().__init__()
        self.name = name
        self.data: dict[int, TBaseIndexNameModel] = {}
        self.cache: dict[int, TBaseIndexNameModel] = {}
        self.indexes: list[int] = []
        self._names: dict[str, int] = {}

    def __getitem__(self, key: Union[int, str]) -> TBaseIndexNameModel:
        if isinstance(key, str):
            return self.get_by_name(key)
        else:
            return self.get_by_index(int(key))

    def __delitem__(self, key: Union[int, str]) -> None:
        if isinstance(key, str):
            if key in self._names and self._names[key] in self.data:
                del self.data[self._names[key]]
                del self._names[key]
        else:
            if int(key) in self.data:
                for n, nidx in self._names.items():
                    if nidx == key:
                        name = n
                        break

                del self.data[int(key)]
                del self._names[name]

    def __setitem__(self, index: int, v: TBaseIndexNameModel) -> None:
        self.data[index] = v

    @verify_thread
    def append(
        self,
        value: TBaseIndexNameModel,
        is_sort: bool = False,
        is_positive_index: bool = True,
    ) -> None:
        if 0 > value.index and is_positive_index:
            value.index = len([k for k in self.data.keys() if k >= 0])

        if value.name and value.name not in self._names:
            # 名前は先勝ちで保持
            self._names[value.name] = value.index

        self.data[value.index] = value
        if is_sort:
            self.sort_indexes()
        else:
            self.indexes.append(value.index)

    @verify_thread
    def remove(
        self, value: TBaseIndexNameModel, is_sort: bool = True
    ) -> dict[int, int]:
        replaced_map: dict[int, int] = {-1: -1}

        if value.index not in self.data:
            return replaced_map

        del self.data[value.index]
        for i in range(len(self.indexes)):
            if self.indexes[i] == value.index:
                del self.indexes[i]
                break
        for i in range(len(self.names)):
            if self.names[i] == value.name:
                del self.names[i]
                break

        # INDEXをずらす
        replaced_map[value.index] = value.index - 1

        # 既に同じINDEXがある場合、前からずらす
        for i in range(value.index + 1, self.last_index + 1):
            v = self.data[i]
            # ズラした結果を保持する
            replaced_map[v.index] = v.index - 1
            v.index -= 1
            # indexをズラして保持
            self.data[v.index] = v
            # 名前逆引きもINDEX置き換え
            self._names[v.name] = v.index
        for i in range(value.index - 1, -1, -1):
            # 範囲外はそのまま
            v = self.data[i]
            replaced_map[v.index] = v.index

        # 最後が重複するので削除する
        del self.data[self.last_index]

        if is_sort:
            self.sort_indexes(is_sort_name=True)

        if replaced_map:
            replaced_map[-1] = -1

        return replaced_map

    @verify_thread
    def insert(
        self,
        value: TBaseIndexNameModel,
        is_sort: bool = True,
        is_positive_index: bool = True,
    ) -> dict[int, int]:
        if 0 > value.index and is_positive_index:
            value.index = len([k for k in self.data.keys() if k >= 0])

        replaced_map: dict[int, int] = {}
        if value.index in self.data:
            # 既に同じINDEXがある場合、後ろからずらす
            for i in range(self.last_index, value.index - 1, -1):
                v = self.data[i]
                # ズラした結果を保持する
                replaced_map[v.index] = v.index + 1
                v.index += 1
                # indexをズラして保持
                self.data[v.index] = v
                # 名前逆引きもINDEX置き換え
                self._names[v.name] = v.index
            for i in range(value.index - 1, -1, -1):
                # 範囲外はそのまま
                v = self.data[i]
                replaced_map[v.index] = v.index
        self.data[value.index] = value

        if value.name and value.name not in self._names:
            # 名前は先勝ちで保持
            self._names[value.name] = value.index

        if is_sort:
            self.sort_indexes()
        else:
            self.indexes.append(value.index)

        if replaced_map:
            replaced_map[-1] = -1

        return replaced_map

    @property
    def names(self) -> list[str]:
        return list(self._names.keys())

    @property
    def last_index(self) -> int:
        return max(self.data.keys()) if self.data else 0

    @property
    def last_name(self) -> str:
        if not self.data:
            return ""
        return self[-1].name

    def range(
        self, start: int = 0, stop: int = -1, step: int = 1
    ) -> list[TBaseIndexNameModel]:
        if 0 > stop:
            # マイナス指定の場合、後ろからの順番に置き換える
            stop = len(self.data) + stop + 1
        return [self.data[self.indexes[n]] for n in range(start, stop, step)]

    @verify_thread
    def get_by_index(self, index: int) -> TBaseIndexNameModel:
        """
        リストから要素を取得する

        Parameters
        ----------
        index : int
            インデックス番号

        Returns
        -------
        TBaseIndexNameModel
            要素
        """
        if 0 <= index:
            return self.data[index]

        # マイナス指定の場合、後ろからの順番に置き換える
        index = len(self.data) + index
        return self.data[self.indexes[index]]

    @verify_thread
    def get_by_name(self, name: str) -> TBaseIndexNameModel:
        """
        リストから要素を取得する

        Parameters
        ----------
        name : str
            名前

        Returns
        -------
        TBaseIndexNameModel
            要素
        """
        return self.data[self._names[name]]

    def sort_indexes(self, is_sort_name: bool = False) -> None:
        self.indexes = sorted(self.data.keys()) if self.data else []
        if is_sort_name:
            self._names = dict(
                [(self.data[index].name, index) for index in self.indexes]
            )

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self) -> Iterator[TBaseIndexNameModel]:
        return iter([self.data[k] for k in sorted(self.data.keys())])

    def __contains__(self, key: Union[int, str]) -> bool:
        if isinstance(key, str):
            return key in self._names
        return int(key) in self.data

    def __bool__(self) -> bool:
        return 0 < len(self.data)

    @verify_thread
    def range_indexes(
        self, index: int, off_flg: bool = False, indexes: Optional[list[int]] = None
    ) -> tuple[int, int, int]:
        """
        指定されたINDEXの前後を返す

        Parameters
        ----------
        index : int
            指定INDEX

        Returns
        -------
        tuple[int, int]
            INDEXがデータ内にある場合: index, index, index
            INDEXがデータ内にない場合: 前のindex, 対象INDEXに相当する場所にあるINDEX, 次のindex
                prev_idx == idx: 指定されたINDEXが一番先頭
                idx == next_idx: 指定されたINDEXが一番最後
        """
        if not indexes:
            indexes = self.indexes
        if not off_flg and (not indexes or index in self.data):
            return index, index, index

        # index がない場合、前後のINDEXを取得する

        idx = bisect_left(indexes, index)

        if 0 == idx:
            prev_index = 0
        else:
            prev_index = indexes[idx - 1]

        if 0 == idx:
            next_index = index
        elif idx == len(indexes):
            next_index = max(indexes)
        else:
            next_index = indexes[idx]

        return (
            prev_index,
            index,
            next_index,
        )

    def cache_clear(self) -> None:
        self.cache = {}


TBaseIndexNameDictModel = TypeVar(
    "TBaseIndexNameDictModel", bound=BaseIndexNameDictModel
)


class BaseIndexNameDictWrapperModel(Generic[TBaseIndexNameDictModel], BaseModel):
    """BaseIndexNameDictModelの辞書基底クラス"""

    __slots__ = (
        "data",
        "cache",
        "_names",
    )

    def __init__(self) -> None:
        """モデル辞書"""
        super().__init__()
        self.data: dict[str, TBaseIndexNameDictModel] = {}
        self.cache: dict[str, TBaseIndexNameDictModel] = {}
        self._names: list[str] = []

    def create(self, key: str) -> TBaseIndexNameDictModel:
        raise NotImplementedError

    def __getitem__(self, key: str) -> TBaseIndexNameDictModel:
        if key not in self.data:
            self.append(self.create(key), name=key)
        return self.data[key]

    def filter(self, *keys: str) -> dict[str, TBaseIndexNameDictModel]:
        return dict([(k, v.copy()) for k, v in self.data.items() if k in keys])

    def __delitem__(self, key: str) -> None:
        if key in self.data:
            del self.data[key]

            for n, name in enumerate(self._names):
                if name == key:
                    del self._names[n]
                    break

    def __setitem__(self, v: TBaseIndexNameDictModel) -> None:
        self.data[v.name] = v

    @verify_thread
    def append(
        self, value: TBaseIndexNameDictModel, name: Optional[str] = None
    ) -> None:
        if not name:
            name = value.last_name

        if name not in self._names:
            self._names.append(name)
        self.data[name] = value

    @property
    def names(self) -> list[str]:
        return self._names

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self) -> Iterator[TBaseIndexNameDictModel]:
        return iter([self.data[k] for k in sorted(self.data.keys())])

    def __contains__(self, key: str) -> bool:
        return key in self._names

    def __bool__(self) -> bool:
        return 0 < len(self.data)


TBaseIndexNameDictWrapperModel = TypeVar(
    "TBaseIndexNameDictWrapperModel", bound=BaseIndexNameDictWrapperModel
)


class BaseHashModel(BaseModel):
    """
    ハッシュ機能付きモデル

    Parameters
    ----------
    path : str, optional
        パス, by  default ""
    """

    __slots__ = ("path", "digest")

    def __init__(self, path: str = "") -> None:
        super().__init__()
        self.path = path
        self.digest = ""

    @property
    def name(self) -> str:
        """モデル内の名前に相当する値を返す"""
        raise NotImplementedError()

    @verify_thread
    def update_digest(self) -> None:
        sha1 = hashlib.sha1()

        with open(self.path, "rb") as f:
            for chunk in iter(lambda: f.read(2048 * sha1.block_size), b""):
                sha1.update(chunk)

        sha1.update(chunk)

        # ファイルパスをハッシュに含める
        sha1.update(self.path.encode(Encoding.UTF_8.value))

        self.digest = sha1.hexdigest()

    @verify_thread
    def delete(self) -> None:
        """削除する準備"""
        pass

    def __bool__(self) -> bool:
        # パスが定義されていたら、中身入り
        return 0 < len(self.path)
