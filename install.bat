@echo off
echo 正在安装Python...
start /wait .\python_installer\python-3.10.4-amd64.exe /quiet InstallAllUsers=1 PrependPath=1

echo 设置临时环境变量...
set "PATH=C:\Program Files\Python310;C:\Program Files\Python310\Scripts;%PATH%"

echo 正在安装依赖...
python -m pip install --no-index --find-links=.\packages -r requirements.txt

echo 安装完成！
pause