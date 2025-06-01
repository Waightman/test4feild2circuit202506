# import streamlit as st
# import pandas as pd
# import numpy as np
# import os
#
# page1 = st.Page("page/feild2circuit.py", title="场路转换")
# page2 = st.Page("page/spice_configure.py", title="电路仿真")
# page3 = st.Page("page/database4aircraft.py", title="复合材料飞机结构电磁屏蔽设计数据库系统设计")
# page4 = st.Page("page/database4aircraft2.py", title="飞机雷电分区和雷电间击环境数据库")
# page5 = st.Page("page/database4aircraft3.py", title="飞机HIRF环境数据库")
# pg = st.navigation([page1, page2, page3,page4,page5])
# pg.run()

import streamlit as st
import pandas as pd
import numpy as np
import os
from streamlit import session_state as state

# 初始化session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# 用户凭据（实际应用中应该加密存储或使用数据库）
USER_CREDENTIALS = {
    "users": {
        "admin": {
            "password": "admin123",
            "access": ["all"]  # 可以访问所有页面
        },
        "engineer": {
            "password": "eng123",
            "access": ["field2circuit", "spice_configure"]  # 只能访问前两个页面
        }
    }
}


def login_page():
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
                st.rerun()  # 使用st.rerun()替代st.experimental_rerun()
            else:
                st.error("用户名或密码错误")


def main_app():
    # 根据用户权限过滤可访问的页面
    available_pages = []

    page1 = st.Page("page/feild2circuit.py", title="场路转换")
    #page2 = st.Page("page/spice_configure.py", title="电路仿真")
    page3 = st.Page("page/database4aircraft.py", title="复合材料飞机结构电磁屏蔽设计数据库系统设计")
    page4 = st.Page("page/database4aircraft2.py", title="飞机雷电分区和雷电间击环境数据库")
    page5 = st.Page("page/database4aircraft3.py", title="飞机HIRF环境数据库")
    all_pages = [page1, page3, page4, page5]
    page_names = ["field2circuit", "spice_configure", "database4aircraft", "database4aircraft2", "database4aircraft3"]

    # 检查用户权限
    if "all" in st.session_state.user_access:
        available_pages = all_pages
    else:
        for i, name in enumerate(page_names):
            if name in st.session_state.user_access:
                available_pages.append(all_pages[i])

    # 添加登出按钮
    st.sidebar.write(f"当前用户: {st.session_state.current_user}")
    if st.sidebar.button("退出登录"):
        st.session_state.authenticated = False
        st.session_state.pop('current_user', None)
        st.session_state.pop('user_access', None)
        st.rerun()  # 使用st.rerun()替代st.experimental_rerun()

    # 显示导航栏
    pg = st.navigation(available_pages)
    pg.run()


# 根据认证状态显示不同内容
if not st.session_state.authenticated:
    login_page()
else:
    main_app()