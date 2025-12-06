import streamlit as st
import os
import base64
import configparser
import sys
from streamlit import session_state as state

# 初始化session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# 读取配置文件
def read_config():
    config = configparser.ConfigParser()
    # 尝试从当前目录读取配置文件
    if os.path.exists('config.ini'):
        config.read('config.ini')
    else:
        # 如果当前目录没有，尝试从程序所在目录读取
        try:
            config.read(os.path.join(os.path.dirname(__file__), 'config.ini'))
        except:
            # 如果都没有，创建默认配置
            config['SERVER'] = {
                'host': '0.0.0.0',
                'port': '8501'
            }
            config['USERS'] = {
                'admin': 'admin123:all',
                'engineer': 'eng123:field2circuit,spice_configure'
            }
            with open('config.ini', 'w') as f:
                config.write(f)
    return config

# 从配置文件加载用户凭据
def load_credentials(config):
    credentials = {"users": {}}
    for user, value in config['USERS'].items():
        parts = value.split(':')
        password = parts[0]
        access = parts[1].split(',') if len(parts) > 1 else []
        credentials["users"][user] = {
            "password": password,
            "access": access
        }
    return credentials

# 获取服务器配置
def get_server_config(config):
    return {
        "host": config['SERVER'].get('host', '0.0.0.0'),
        "port": config['SERVER'].getint('port', 8501)
    }

# 读取配置
config = read_config()
USER_CREDENTIALS = load_credentials(config)
SERVER_CONFIG = get_server_config(config)

def image_to_base64(image_path):
    """将图片转换为base64编码"""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

LOGO_PATH = "company_logo.jpg"

def login_page():
    # 检查图片是否存在
    if not os.path.exists(LOGO_PATH):
        st.error("公司logo图片未找到，请确保company_logo.jpg文件存在")
        logo_html = ""
    else:
        logo_base64 = image_to_base64(LOGO_PATH)
        logo_html = f"""
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
            <img src="data:image/jpeg;base64,{logo_base64}" alt="公司标徽" style="height: 60px;">
            <h3 style="margin: 0; font-size: 42px;">中航通飞华南飞机工业有限公司</h3>
        </div>
        """

    # 登录页面布局
    st.markdown(logo_html, unsafe_allow_html=True)
    st.title("飞机电磁设计系统登录")

    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录")

        if submitted:
            if username in USER_CREDENTIALS["users"] and password == USER_CREDENTIALS["users"][username]["password"]:
                st.session_state.authenticated = True
                st.session_state.current_user = username
                st.session_state.user_access = USER_CREDENTIALS["users"][username]["access"]
                st.rerun()
            else:
                st.error("用户名或密码错误")

def main_app():
    # 用户信息和登出按钮
    st.sidebar.write(f"当前用户: {st.session_state.current_user}")
    if st.sidebar.button("退出登录"):
        st.session_state.authenticated = False
        st.session_state.pop('current_user', None)
        st.session_state.pop('user_access', None)
        st.rerun()

    # 根据用户权限过滤可访问的页面
    available_pages = []
    page1 = st.Page("page/feild2circuit.py", title="场路转换")
    page3 = st.Page("page/database4aircraft.py", title="复合材料飞机结构电磁屏蔽设计数据库系统设计")
    page4 = st.Page("page/database4aircraft2.py", title="飞机雷电分区和雷电间击环境数据库")
    page5 = st.Page("page/database4aircraft3.py", title="飞机HIRF环境数据库")
    all_pages = [page1, page3, page4, page5]
    page_names = ["field2circuit", "spice_configure", "database4aircraft", "database4aircraft2", "database4aircraft3"]

    if "all" in st.session_state.user_access:
        available_pages = all_pages
    else:
        for i, name in enumerate(page_names):
            if name in st.session_state.user_access:
                available_pages.append(all_pages[i])

    # 显示导航栏
    pg = st.navigation(available_pages)
    pg.run()

def main():
    # 根据认证状态显示不同内容
    if not st.session_state.authenticated:
        login_page()
    else:
        main_app()

if __name__ == "__main__":
    # 保存原始sys.argv
    original_argv = sys.argv.copy()

    try:
        # 设置Streamlit运行参数
        sys.argv = [
            "streamlit", "run", __file__,
            f"--server.address={SERVER_CONFIG['host']}",
            f"--server.port={SERVER_CONFIG['port']}"
        ]

        # 调用主函数
        main()
    finally:
        # 恢复原始sys.argv
        sys.argv = original_argv