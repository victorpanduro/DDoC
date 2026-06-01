from typing import TypedDict

type APODCache = dict[str, APODData]

class APODData(TypedDict):
    title: str
    date: str
    explanation: str
    url: str
    media_type: str
    copyright: str
