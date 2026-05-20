from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from server.state import get_engine


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
