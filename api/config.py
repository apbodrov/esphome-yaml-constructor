import asyncio
import os
import subprocess
import uuid

from fastapi import APIRouter, status, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTasks
from starlette.responses import JSONResponse, FileResponse

from db.connect import get_db
from db.schemas import SaveConfigResponse
from lib.methods import save_file_to_uploads, read_stream, get_info_config, post_compile_process
from lib.config import _get_yamlconfig_by_hash, _create_new_yaml_config, _update_config, \
    get_config_by_name_or_hash
from settings import UPLOADED_FILES_PATH, COMPILE_CMD, COMPILE_DIR

config_router = APIRouter()


@config_router.post("/validate", status_code=status.HTTP_200_OK)
async def validate(
        request: Request,
        background_tasks: BackgroundTasks = BackgroundTasks()
):
    file_name = str(uuid.uuid4())
    await save_file_to_uploads(request, file_name)
    cmd = ['esphome', 'config', f'{UPLOADED_FILES_PATH}{file_name}.yaml']
    # compilation process
    process = await asyncio.to_thread(subprocess.Popen, cmd,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # line-by-line output of logs (generator)
    otv = read_stream(process.stdout)
    # deleting the created yaml file
    background_tasks.add_task(os.remove, f'{UPLOADED_FILES_PATH}{file_name}.yaml')
    return StreamingResponse(otv, media_type="text/plain")


@config_router.post("/save_config", status_code=status.HTTP_200_OK)
async def save_config(request: Request, db: AsyncSession = Depends(get_db)):
    if await request.json() is None:
        raise HTTPException(status_code=404, detail="Item not found")
    config_info_db = await get_info_config(request)

    old_file_info_from_db = await _get_yamlconfig_by_hash(hash_yaml=config_info_db['hash_yaml'], session=db)
    if old_file_info_from_db is None:
        info_old_hash = await get_config_by_name_or_hash(hash_yaml=config_info_db['hash_yaml'], session=db)
        if info_old_hash is not None:
            name_config = await _update_config(hash_yaml=config_info_db['hash_yaml'],
                                               name_esphome=config_info_db['name_esphome'],
                                               platform=config_info_db['platform'], session=db)

        else:
            new_yaml_config = await _create_new_yaml_config(session=db, name_esphome=config_info_db['name_esphome'],
                                                            hash_yaml=config_info_db['hash_yaml'],
                                                            platform=config_info_db['platform'])
            name_config = new_yaml_config.name_config
        await save_file_to_uploads(request, file_name=name_config)
        return SaveConfigResponse(name_config=name_config)
    else:
        if not os.path.isfile(f"{UPLOADED_FILES_PATH}{old_file_info_from_db.name_config}.yaml"):
            await save_file_to_uploads(request, file_name=old_file_info_from_db.name_config)
        return SaveConfigResponse(name_config=old_file_info_from_db.name_config)


@config_router.post("/compile", status_code=status.HTTP_200_OK)
async def compile_file(request: Request, db: AsyncSession = Depends(get_db),
                       background_tasks: BackgroundTasks = BackgroundTasks()):
    file_name = (await request.body()).decode('utf-8')
    info_config = await get_config_by_name_or_hash(name_config=file_name, session=db)
    if file_name == '':
        return JSONResponse(
            status_code=400,
            content={"message": f"Config not save"},
        )
    elif info_config is None:
        return JSONResponse(
            status_code=404,
            content={"message": f"Config not save!"},
        )

    cmd = f"{COMPILE_CMD} {UPLOADED_FILES_PATH}{file_name}.yaml"
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    if info_config.name_esphome == '' or info_config.name_esphome is None:
        return StreamingResponse(read_stream(process.stdout), media_type='text/event-stream')
    else:
        background_tasks.add_task(post_compile_process, file_name, db)
        return StreamingResponse(read_stream(process.stdout), media_type='text/event-stream')


@config_router.post("/download", status_code=status.HTTP_200_OK)
async def download_bin(
        request: Request,
):
    # get information about the file, delete the yaml file, return the binary to the user
    file_name = (await request.body()).decode('utf-8')
    if not file_name:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                'message': 'The configuration was not compiled'
            }
        )
    elif not os.path.exists(f'{COMPILE_DIR}{file_name}.bin'):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                'message': 'The configuration was not compiled'
            }
        )
    else:
        return FileResponse(f"compile_files/{file_name}.bin",
                            filename=f"{file_name}.bin",
                            media_type="application/octet-stream")
