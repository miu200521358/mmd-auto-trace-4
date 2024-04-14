from PIL import Image
from mlib.core.base import FileType
from mlib.core.collection import BaseHashModel
from mlib.core.reader import BaseReader


class ImageModel(BaseHashModel):
    def __init__(
        self,
        path: str = "",
    ):
        super().__init__(path=path or "")
        self.image = None


class ImageReader(BaseReader[ImageModel]):
    def __init__(self) -> None:
        super().__init__()

    def create_model(self, path: str) -> ImageModel:
        return ImageModel(path=path)

    def read_by_filepath(self, path: str) -> ImageModel:
        # モデルを新規作成
        model: ImageModel = self.create_model(path)
        model.image = Image.open(path).convert("RGBA")

        return model

    def read_by_buffer_header(self, model: ImageModel):
        pass

    def read_by_buffer(self, model: ImageModel):
        pass

    @property
    def file_wildcard(self) -> str:
        return FileType.IMAGE.value

    @property
    def file_ext(self) -> str:
        return FileType.IMAGE.name.lower()

    @property
    def file_type(self) -> FileType:
        return FileType.IMAGE
