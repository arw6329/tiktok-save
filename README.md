# TikTokSlideshow-Downloader

Script to automatically download all of your liked and bookmarked videos from TikTok using Python, Selenium, and Docker

##  Requirements

- Docker
- A linux system with a display (for showing the TikTok login page in a browser)

## Usage

1. Request a copy of your data from the TikTok app at Settings and Privacy > Account > Download your data. Make sure the download file format is JSON (not TXT). It may take a few days for the download to be ready.

2. Launch the script using docker:

```bash
# make sure cookies.json exists if this is the first time running
touch cookies.json

docker run --rm -it -v /tmp/.X11-unix:/tmp/.X11-unix -e "DISPLAY=${DISPLAY:-:0.0}" \
    -v './user.json:/json' \
    -v './out:/out' \
    -v './cookies.json:/cookies' \
    -v './logs:/logs' \
    ghcr.io/arw6329/tiktok-save:main
```

3. Log in to TikTok when the browser window opens. It should then close automatically and start downloading.

This assumes the JSON file downloaded above is available at `./user.json`. Adjust mounts if necessary.

Bookmarked content will be saved to `./out/Bookmarked` and liked content saved to `./out/Liked`. Videos will be saved as `<id>.mp4`, for example `7348616153331256619.mp4`. Slideshows will be saved as images in a numeric folder with each image image having file name `<index>.jpg`; for example a 3-image slideshow with id 7348616153331256619 will be saved in folder `7348616153331256619` with 3 files `01.jpg`, `02.jpg`, `03.jpg`. Slideshow audio is not yet downloaded.

Your cookies will be saved to `./cookies.json` and used next time the script is ran so you will not have to log in again.

# Build from source

You can build the docker image from source instead of pulling it:

```bash
git clone https://github.com/arw6329/tiktok-save.git
cd tiktok-save

docker build -t tiktok-save .

touch cookies.json

docker run --rm -it -v /tmp/.X11-unix:/tmp/.X11-unix -e "DISPLAY=${DISPLAY:-:0.0}" \
    -v './user.json:/json' \
    -v './out:/out' \
    -v './cookies.json:/cookies' \
    -v './logs:/logs' \
    tiktok-save
```

# Run with python

You can run the python script directly instead of using docker, although I have not tested this outside docker:

```bash
pip install -r requirements.txt
python main.py --output out --userjson user.json --cookies cookies.json --logs logs
```

This requires Chrome to be installed on the host:

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt update
apt install -y ./google-chrome-stable_current_amd64.deb
```
