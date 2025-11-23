Jellfin-cli
-----------

Access jellfin through CLI. This is useful in case when browser
is unable to decode particular stream and server is not
configured for transcoding. The cli allows navigation through
the media stored on the server and can open the stream
directly in the vlc media player

Usage
-----
A config.json is expected in the directory of binary with below structure

    {
        "AuthKey":"<authkey>",  // can be obtained from API keys section in dashboard
        "Host":"<server-url>",  // without the trailing slash
        "UserId":"<userid>" // can be obtained from browser API requests
    }
