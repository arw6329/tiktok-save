# modified from https://github.com/peppapig450/TikTokSlideshow-Downloader

import logging
import argparse
import itertools
import json
from pathlib import Path
from enum import Enum
from collections import OrderedDict
import datetime

import requests
import yt_dlp
from bs4 import BeautifulSoup
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class PageType(Enum):
    VIDEO = 1
    SLIDESHOW = 2
    UNAVAILABLE = 3
    UNKNOWN = 4


def get_id_from_tiktok_link(link: str):
    id = list(filter(lambda x: x.strip(), link.split("/")))[-1]

    if len(id) <= 0 or not id.isdigit():
        raise Exception(f"Id {id} from url {link} is not valid")
    
    return id


def load_tiktok_page(driver: Chrome, url: str) -> tuple[PageType, str]:
    driver.get(url)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "video, .css-brxox6-ImgPhotoSlide.e10jea832, .css-1osbocj-DivErrorContainer")
        )
    )

    if driver.find_elements(By.CSS_SELECTOR, ".css-brxox6-ImgPhotoSlide.e10jea832"):
        return (PageType.SLIDESHOW, driver.page_source)
    elif driver.find_elements(By.XPATH, "//*[contains(@class,'.css-1osbocj-DivErrorContainer') and contains(text(),'Video currently unavailable')]"):
        return (PageType.UNAVAILABLE, None)
    elif driver.find_elements(By.CSS_SELECTOR, "video"):
        return (PageType.VIDEO, None)
    else:
        return (PageType.UNKNOWN, None)


def cookies_list_to_netscape(cookies: list, netscape_file: Path):
   with open(netscape_file, "w") as file:
        file.write("# Netscape HTTP Cookie File\n")
        file.write("# This file is generated by a script\n\n")

        for cookie in cookies:
            domain: str = cookie["domain"]
            flag = "TRUE" if domain.startswith(".") else "FALSE"
            path: str = cookie.get("path", "/")
            secure = "TRUE" if cookie["secure"] else "FALSE"
            expiry = int(cookie.get("expiry", "0"))
            name: str = cookie["name"]
            value = cookie["value"]

            file.write(
                f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n"
            )


def launch_chrome(headless: bool):
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("start-maximized")
    options.add_argument("enable-automation")
    options.add_argument("--disable-blink-features=AutomationControlled")

    if headless:
        options.add_argument("--headless")

    driver = Chrome(
        options=options, service=ChromeService(ChromeDriverManager().install())
    )
    driver.get("https://www.tiktok.com/")

    return driver


def get_driver(cookies_path: Path):
    if cookies_path.exists() and cookies_path.stat().st_size > 0:
        logger.info("Using existing cookies")
        
    else:
        logger.info("Cookies not found, waiting for manual login")

        driver = launch_chrome(False)

        # wait until logged in
        wait = WebDriverWait(driver, 120)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '[data-e2e="following-accounts"]')))

        logger.info("Logged in, saving cookies...")

        with open(cookies_path, "w") as f:
            f.write(json.dumps(driver.get_cookies()))

        driver.quit()

    driver = launch_chrome(True)

    cookies = []
    with open(cookies_path, "r") as f:
        cookies = json.loads(f.read())

    driver.delete_all_cookies()

    for cookie in cookies:
        driver.add_cookie(cookie)

    logger.info("Checking login...")

    driver.refresh()

    wait = WebDriverWait(driver, 10)
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '[data-e2e="following-accounts"]')))

    logger.info("Driver ready")

    return driver


def parse_slideshow_links(html):
    soup = BeautifulSoup(html, "html.parser")
    image_tags = soup.select(".css-brxox6-ImgPhotoSlide.e10jea832")
    image_links = [img["src"] for img in image_tags if "src" in img.attrs]

    # Flatten any nested lists, make unique
    flat_image_links = list(OrderedDict.fromkeys(
        itertools.chain(
            *[
                sublist if isinstance(sublist, list) else [sublist]
                for sublist in image_links
            ]
        )
    ))

    return flat_image_links


def download_images(image_links: list[str], output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir()

    for i, link in enumerate(image_links, 1):
        try:
            response = requests.get(link, stream=True)
            response.raise_for_status()
            file_name = link.split("/")[-1].split("?")[0]
            file_path = output_dir / ".".join([str(i).zfill(2), 'jpg'])
            with file_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            logger.info(f"Downloaded image: {file_name}")
        except requests.RequestException as e:
            logger.error(f"Failed to download {link}: {e}")


def download_video(url, output_dir, cookies):
    cookies_file = "/tmp/cookies"
    cookies_list_to_netscape(cookies, cookies_file)

    ydl_opts = {
        "outtmpl": f"{output_dir}/%(id)s.%(ext)s",
        "format": "best[vcodec!=none]",
        "noplaylist": True,
        "quiet": False,
        "cookiefile": cookies_file
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        logger.error(f"Failed to download video {get_id_from_tiktok_link(url)}: {e}")


def download_tiktok_link(link: str, outfolder: Path, driver: Chrome, cookies: list):
    logger.info(f"Downloading link {link}")

    id = get_id_from_tiktok_link(link)

    if any(file.name.startswith(id) for file in outfolder.iterdir()):
        logger.info(f"Skipping post {id}: file already exists")
        return

    page_type, html = load_tiktok_page(driver, link)

    match page_type:
        case PageType.VIDEO:
            logger.info(f"Downloading video {id}")
            download_video(link, outfolder, cookies)

        case PageType.SLIDESHOW:
            image_links = parse_slideshow_links(html)

            if len(image_links) == 0:
                logger.error(f"Slideshow {id} had 0 images")
                return

            image_folder = outfolder / id

            logger.info(f"Downloading {len(image_links)} images for slideshow {id}")
            download_images(image_links, image_folder)

        case PageType.UNAVAILABLE:
            logger.info(f"Skipping video {id} because post was deleted or is unavailable")

        case _:
            logger.error(f"Skipping video {id} because page type was unknown")


def main():
    parser = argparse.ArgumentParser(description="Download TikTok videos and slideshow images")
    parser.add_argument(
        "--output", required=True, help="Output folder for downloaded content"
    )
    parser.add_argument(
        "--userjson", required=True, help="JSON file of user TikTok data"
    )
    parser.add_argument(
        "--cookies", required=True, help="Cookies JSON file to use to log in, or file to save cookies to after logging in"
    )
    parser.add_argument(
        "--logs", required=True, help="Directory to save logs to"
    )
    args = parser.parse_args()

    log_folder = Path(args.logs) / datetime.datetime.now().strftime("%y:%d:%m %H:%M:%S")
    log_folder.mkdir()
    logging.basicConfig(level=logging.INFO, handlers=[ logging.StreamHandler(), logging.FileHandler(log_folder / "/main.log") ])

    driver = get_driver(Path(args.cookies))
    cookies = driver.get_cookies()

    user_data_json = None
    with open(args.userjson, 'r') as f:
        user_data_json = json.loads(f.read())

    liked_videos_links = map(lambda elem: elem['Link'], user_data_json['Activity']['Like List']['ItemFavoriteList'])
    
    outfolder = Path(args.output) / "Liked"
    outfolder.mkdir(exist_ok=True)

    for link in liked_videos_links:
        download_tiktok_link(link, outfolder, driver, cookies)
    
    bookmarked_videos_links = map(lambda elem: elem['Link'], user_data_json['Activity']['Favorite Videos']['FavoriteVideoList'])

    outfolder = Path(args.output) / "Bookmarked"
    outfolder.mkdir(exist_ok=True)

    for link in bookmarked_videos_links:
        download_tiktok_link(link, outfolder, driver, cookies)


if __name__ == "__main__":
    main()
