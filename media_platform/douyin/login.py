# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/douyin/login.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


import asyncio
import functools
import sys
from typing import Optional

from playwright.async_api import BrowserContext, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from tenacity import (RetryError, retry, retry_if_result, stop_after_attempt,
                      wait_fixed)

import config
from base.base_crawler import AbstractLogin
from cache.cache_factory import CacheFactory
from tools import utils


class DouYinLogin(AbstractLogin):

    def __init__(self,
                 login_type: str,
                 browser_context: BrowserContext, # type: ignore
                 context_page: Page, # type: ignore
                 login_phone: Optional[str] = "",
                 cookie_str: Optional[str] = ""
                 ):
        config.LOGIN_TYPE = login_type
        self.browser_context = browser_context
        self.context_page = context_page
        self.login_phone = login_phone
        self.scan_qrcode_time = 60
        self.cookie_str = cookie_str

    async def begin(self):
        """
            Start login douyin website
            The verification accuracy of the slider verification is not very good... If there are no special requirements, it is recommended not to use Douyin login, or use cookie login
        """

        # popup login dialog
        # 先看是否已经处于登录态（例如复用本地 user-data-dir 且 cookie 仍在有效期）。
        # 已登录时直接跳过弹窗 + 扫码流程，避免每次启动都强制重新登录。
        if await self._is_already_logged_in():
            utils.logger.info(
                "[DouYinLogin.begin] 检测到已是登录态，跳过扫码登录流程"
            )
            return

        # 抖音页面加载后可能有一个“点击登录/关注”的浮层遮住右上角登录按钮。
        # 这里先尝试把它关掉，否则后续点击“登录”按钮会被浮层拦截而失败。
        await self._dismiss_overlays()

        await self.popup_login_dialog()
        await self._dismiss_overlays()

        # select login type
        if config.LOGIN_TYPE == "qrcode":
            await self.login_by_qrcode()
        elif config.LOGIN_TYPE == "phone":
            await self.login_by_mobile()
        elif config.LOGIN_TYPE == "cookie":
            await self.login_by_cookies()
        else:
            raise ValueError("[DouYinLogin.begin] Invalid Login Type Currently only supported qrcode or phone or cookie ...")

        # If the page redirects to the slider verification page, need to slide again
        await asyncio.sleep(6)
        current_page_title = await self.context_page.title()
        if "验证码中间页" in current_page_title:
            await self.check_page_display_slider(move_step=3, slider_level="hard")

        # check login state
        utils.logger.info(f"[DouYinLogin.begin] login finished then check login state ...")
        try:
            await self.check_login_state()
        except RetryError:
            utils.logger.info("[DouYinLogin.begin] login failed please confirm ...")
            sys.exit()

        # wait for redirect
        wait_redirect_seconds = 5
        utils.logger.info(f"[DouYinLogin.begin] Login successful then wait for {wait_redirect_seconds} seconds redirect ...")
        await asyncio.sleep(wait_redirect_seconds)

    @retry(stop=stop_after_attempt(600), wait=wait_fixed(1), retry=retry_if_result(lambda value: value is False))
    async def check_login_state(self):
        """Check if the current login status is successful and return True otherwise return False"""
        current_cookie = await self.browser_context.cookies()
        _, cookie_dict = utils.convert_cookies(current_cookie)

        for page in self.browser_context.pages:
            try:
                local_storage = await page.evaluate("() => window.localStorage")
                if local_storage.get("HasUserLogin", "") == "1":
                    return True
            except Exception as e:
                # utils.logger.warn(f"[DouYinLogin] check_login_state waring: {e}")
                await asyncio.sleep(0.1)

        if cookie_dict.get("LOGIN_STATUS") == "1":
            return True

        return False

    async def _is_already_logged_in(self) -> bool:
        """判断当前浏览器上下文是否已是登录态。

        依据：localStorage.HasUserLogin == '1' 或 cookie.LOGIN_STATUS == '1'。
        任一命中即认为已登录（与 check_login_state 的判定口径保持一致），
        此时无需重新扫码。
        """
        try:
            current_cookie = await self.browser_context.cookies()
            _, cookie_dict = utils.convert_cookies(current_cookie)
            if cookie_dict.get("LOGIN_STATUS") == "1":
                return True
        except Exception as e:
            utils.logger.debug(f"[DouYinLogin._is_already_logged_in] read cookies failed: {e}")

        for page in self.browser_context.pages:
            try:
                local_storage = await page.evaluate("() => window.localStorage")
                if local_storage.get("HasUserLogin", "") == "1":
                    return True
            except Exception:
                continue
        return False

    async def _dismiss_overlays(self) -> None:
        """尝试关闭首页遮挡登录按钮的浮层（登录引导/下载 App 等）。

        这些浮层会把右上角 pacing“登录”按钮盖住，导致点击被拦截。
        这里用短超时尝试多个关闭按钮，失败不影响主流程。
        """
        close_selectors = [
            "xpath=//div[@id='douyin-header-login-guide']//*[local-name()='svg']",
            "xpath=//div[contains(@class,'login-guide')]//*[local-name()='svg']",
            "xpath=//div[contains(@class,'guide-close')]",
            "xpath=//*[contains(@class,'close-icon')]",
            "xpath=//*[contains(@class,'close') and (self::span or self::div or self::i)]",
        ]
        for sel in close_selectors:
            try:
                loc = self.context_page.locator(sel).first
                if await loc.count() == 0:
                    continue
                if not await loc.is_visible(timeout=300):
                    continue
                await loc.click(timeout=1000, force=True)
                utils.logger.info(f"[DouYinLogin._dismiss_overlays] closed overlay via {sel}")
                await asyncio.sleep(0.3)
            except Exception:
                continue

    async def popup_login_dialog(self):
        """If the login dialog box does not pop up automatically, we will manually click the login button.

        健壮性改造（针对抖音改版）：
        1. 登录弹窗可能不再使用旧的 id `login-panel-new`，也可能根本不自动弹出；
        2. 首页右上角的“登录”按钮位于 <pace-island> 岛容器里，直接 click() 在元素被
           遮罩/弹窗覆盖时会因 Playwright 的 actionability 检查（元素不可点击）一直等到
           30s 超时，抛出 Locator.click: Timeout。
        因此这里改为：多重选择器探测 + 多种点击兜底（普通 click -> force click -> JS click -> 坐标点击），
        确保能弹出登录弹窗。
        """
        # 兼容新旧登录弹窗容器，只要其中一个可见即认为弹窗已出现
        dialog_selectors = [
            "xpath=//div[@id='login-panel-new']",
            "xpath=//div[contains(@id, 'douyin_login_comp')]",
            "xpath=//*[contains(@class, 'login-container')]",
            "xpath=//article[contains(@class, 'web-login')]",
        ]

        async def _dialog_visible() -> bool:
            for sel in dialog_selectors:
                try:
                    loc = self.context_page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible(timeout=500):
                        return True
                except Exception:
                    continue
            return False

        # 先等最多 6 秒，看弹窗是否自动弹出
        for _ in range(12):
            if await _dialog_visible():
                utils.logger.info("[DouYinLogin.popup_login_dialog] login dialog box popped up automatically")
                return
            await asyncio.sleep(0.5)

        utils.logger.info(
            "[DouYinLogin.popup_login_dialog] login dialog box does not pop up automatically, "
            "we will manually click the login button"
        )

        # “登录”按钮文案定位：优先精确匹配，其次模糊匹配
        login_button_xpaths = [
            "xpath=//p[normalize-space(text())='登录']",
            "xpath=//span[normalize-space(text())='登录']",
            "xpath=//button[normalize-space(.)='登录']",
            "xpath=//div[normalize-space(text())='登录']",
            "xpath=//*[normalize-space(text())='登录']",
        ]

        clicked = False
        for xpath in login_button_xpaths:
            try:
                loc = self.context_page.locator(xpath).first
                if await loc.count() == 0:
                    continue
                try:
                    # 1) 常规点击（带短超时，避免卡 30s）
                    await loc.click(timeout=3000)
                    clicked = True
                    utils.logger.info(
                        f"[DouYinLogin.popup_login_dialog] clicked login button via {xpath}"
                    )
                    break
                except Exception as click_err:
                    utils.logger.info(
                        f"[DouYinLogin.popup_login_dialog] normal click failed ({click_err}), "
                        f"falling back to force click for {xpath}"
                    )
                    # 2) force 点击，跳过遮挡/可点击性检查
                    try:
                        await loc.click(timeout=3000, force=True)
                        clicked = True
                        utils.logger.info(
                            f"[DouYinLogin.popup_login_dialog] force-clicked login button via {xpath}"
                        )
                        break
                    except Exception as force_err:
                        utils.logger.info(
                            f"[DouYinLogin.popup_login_dialog] force click failed ({force_err}), "
                            f"falling back to JS click for {xpath}"
                        )
                        # 3) JS 直接触发 click 事件
                        try:
                            await loc.evaluate("el => el.click()")
                            clicked = True
                            utils.logger.info(
                                f"[DouYinLogin.popup_login_dialog] JS-clicked login button via {xpath}"
                            )
                            break
                        except Exception as js_err:
                            utils.logger.info(
                                f"[DouYinLogin.popup_login_dialog] JS click failed: {js_err}"
                            )
                            continue
            except Exception as e:
                utils.logger.info(f"[DouYinLogin.popup_login_dialog] locate {xpath} failed: {e}")
                continue

        if not clicked:
            utils.logger.error(
                "[DouYinLogin.popup_login_dialog] failed to click login button with all strategies. "
                "Please check the Douyin homepage manually."
            )
            return

        # 等待弹窗出现（最多 8 秒）
        for _ in range(16):
            await asyncio.sleep(0.5)
            if await _dialog_visible():
                utils.logger.info("[DouYinLogin.popup_login_dialog] login dialog box appeared after click")
                return
        utils.logger.error(
            "[DouYinLogin.popup_login_dialog] login dialog box still not visible after clicking login button"
        )

    async def login_by_qrcode(self):
        utils.logger.info("[DouYinLogin.login_by_qrcode] Begin login douyin by qrcode...")

        # 抖音改版后二维码容器 id 可能变化，这里尝试多个候选选择器；
        # 并先给弹窗一点渲染时间（二维码通常是异步加载出来的）。
        qrcode_selectors = [
            "xpath=//div[@id='animate_qrcode_container']//img",
            "xpath=//div[contains(@id, 'qrcode')]//img",
            "xpath=//div[contains(@class, 'qrcode')]//img",
            "xpath=//img[contains(@class, 'qrcode')]",
            "xpath=//div[@id='login-panel-new']//canvas",
            "xpath=//div[contains(@class, 'login')]//canvas",
        ]

        base64_qrcode_img = None
        for _ in range(10):  # 最多等 5 秒
            for sel in qrcode_selectors:
                try:
                    base64_qrcode_img = await utils.find_login_qrcode(
                        self.context_page, selector=sel
                    )
                except Exception:
                    base64_qrcode_img = None
                if base64_qrcode_img:
                    utils.logger.info(
                        f"[DouYinLogin.login_by_qrcode] found qrcode via selector: {sel}"
                    )
                    break
            if base64_qrcode_img:
                break
            # 若弹窗还没出现或仍在“验证码登录” tab，尝试切回扫码 tab
            try:
                scan_tab = self.context_page.locator("xpath=//span[text()='扫码登录']").first
                if await scan_tab.count() > 0:
                    await scan_tab.click(timeout=1500)
            except Exception:
                pass
            await asyncio.sleep(0.5)

        if not base64_qrcode_img:
            utils.logger.info("[DouYinLogin.login_by_qrcode] login qrcode not found please confirm ...")
            sys.exit()

        partial_show_qrcode = functools.partial(utils.show_qrcode, base64_qrcode_img)
        asyncio.get_running_loop().run_in_executor(executor=None, func=partial_show_qrcode)
        await asyncio.sleep(2)

    async def login_by_mobile(self):
        utils.logger.info("[DouYinLogin.login_by_mobile] Begin login douyin by mobile ...")
        mobile_tap_ele = self.context_page.locator("xpath=//li[text() = '验证码登录']")
        await mobile_tap_ele.click()
        await self.context_page.wait_for_selector("xpath=//article[@class='web-login-mobile-code']")
        mobile_input_ele = self.context_page.locator("xpath=//input[@placeholder='手机号']")
        await mobile_input_ele.fill(self.login_phone)
        await asyncio.sleep(0.5)
        send_sms_code_btn = self.context_page.locator("xpath=//span[text() = '获取验证码']")
        await send_sms_code_btn.click()

        # Check if there is slider verification
        await self.check_page_display_slider(move_step=10, slider_level="easy")
        cache_client = CacheFactory.create_cache(config.CACHE_TYPE_MEMORY)
        max_get_sms_code_time = 60 * 2  # Maximum time to get verification code is 2 minutes
        while max_get_sms_code_time > 0:
            utils.logger.info(f"[DouYinLogin.login_by_mobile] get douyin sms code from redis remaining time {max_get_sms_code_time}s ...")
            await asyncio.sleep(1)
            sms_code_key = f"dy_{self.login_phone}"
            sms_code_value = cache_client.get(sms_code_key)
            if not sms_code_value:
                max_get_sms_code_time -= 1
                continue

            sms_code_input_ele = self.context_page.locator("xpath=//input[@placeholder='请输入验证码']")
            await sms_code_input_ele.fill(value=sms_code_value.decode())
            await asyncio.sleep(0.5)
            submit_btn_ele = self.context_page.locator("xpath=//button[@class='web-login-button']")
            await submit_btn_ele.click()  # Click login
            # todo ... should also check the correctness of the verification code, it may be incorrect
            break

    async def check_page_display_slider(self, move_step: int = 10, slider_level: str = "easy"):
        """
        Check if slider verification appears on the page
        :return:
        """
        # Wait for slider verification to appear
        back_selector = "#captcha-verify-image"
        try:
            await self.context_page.wait_for_selector(selector=back_selector, state="visible", timeout=30 * 1000)
        except PlaywrightTimeoutError:  # No slider verification, return directly
            return

        gap_selector = 'xpath=//*[@id="captcha_container"]/div/div[2]/img[2]'
        max_slider_try_times = 20
        slider_verify_success = False
        while not slider_verify_success:
            if max_slider_try_times <= 0:
                utils.logger.error("[DouYinLogin.check_page_display_slider] slider verify failed ...")
                sys.exit()
            try:
                await self.move_slider(back_selector, gap_selector, move_step, slider_level)
                await asyncio.sleep(1)

                # If the slider is too slow or verification failed, it will prompt "The operation is too slow", click the refresh button here
                page_content = await self.context_page.content()
                if "操作过慢" in page_content or "提示重新操作" in page_content:
                    utils.logger.info("[DouYinLogin.check_page_display_slider] slider verify failed, retry ...")
                    await self.context_page.click(selector="//a[contains(@class, 'secsdk_captcha_refresh')]")
                    continue

                # After successful sliding, wait for the slider to disappear
                await self.context_page.wait_for_selector(selector=back_selector, state="hidden", timeout=1000)
                # If the slider disappears, it means the verification is successful, break the loop. If not, it means the verification failed, the above line will throw an exception and be caught to continue the loop
                utils.logger.info("[DouYinLogin.check_page_display_slider] slider verify success ...")
                slider_verify_success = True
            except Exception as e:
                utils.logger.error(f"[DouYinLogin.check_page_display_slider] slider verify failed, error: {e}")
                await asyncio.sleep(1)
                max_slider_try_times -= 1
                utils.logger.info(f"[DouYinLogin.check_page_display_slider] remaining slider try times: {max_slider_try_times}")
                continue

    async def move_slider(self, back_selector: str, gap_selector: str, move_step: int = 10, slider_level="easy"):
        """
        Move the slider to the right to complete the verification
        :param back_selector: Selector for the slider verification background image
        :param gap_selector:  Selector for the slider verification slider
        :param move_step: Controls the ratio of single movement speed, default is 1, meaning the distance moves in 0.1 seconds no matter how far, larger value means slower
        :param slider_level: Slider difficulty easy hard, corresponding to the slider for mobile verification code and the slider in the middle of verification code
        :return:
        """

        # get slider background image
        slider_back_elements = await self.context_page.wait_for_selector(
            selector=back_selector,
            timeout=1000 * 10,  # wait 10 seconds
        )
        slide_back = str(await slider_back_elements.get_property("src")) # type: ignore

        # get slider gap image
        gap_elements = await self.context_page.wait_for_selector(
            selector=gap_selector,
            timeout=1000 * 10,  # wait 10 seconds
        )
        gap_src = str(await gap_elements.get_property("src")) # type: ignore

        # Identify slider position
        slide_app = utils.Slide(gap=gap_src, bg=slide_back)
        distance = slide_app.discern()

        # Get movement trajectory
        tracks = utils.get_tracks(distance, slider_level)
        new_1 = tracks[-1] - (sum(tracks) - distance)
        tracks.pop()
        tracks.append(new_1)

        # Drag slider to specified position according to trajectory
        element = await self.context_page.query_selector(gap_selector)
        bounding_box = await element.bounding_box() # type: ignore

        await self.context_page.mouse.move(bounding_box["x"] + bounding_box["width"] / 2, # type: ignore
                                           bounding_box["y"] + bounding_box["height"] / 2) # type: ignore
        # Get x coordinate center position
        x = bounding_box["x"] + bounding_box["width"] / 2 # type: ignore
        # Simulate sliding operation
        await element.hover() # type: ignore
        await self.context_page.mouse.down()

        for track in tracks:
            # Loop mouse movement according to trajectory
            # steps controls the ratio of single movement speed, default is 1, meaning the distance moves in 0.1 seconds no matter how far, larger value means slower
            await self.context_page.mouse.move(x + track, 0, steps=move_step)
            x += track
        await self.context_page.mouse.up()

    async def login_by_cookies(self):
        utils.logger.info("[DouYinLogin.login_by_cookies] Begin login douyin by cookie ...")
        for key, value in utils.convert_str_cookie_to_dict(self.cookie_str).items():
            await self.browser_context.add_cookies([{
                'name': key,
                'value': value,
                'domain': ".douyin.com",
                'path': "/"
            }])
