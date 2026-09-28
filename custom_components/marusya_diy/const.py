from typing import Final

DOMAIN: Final = "marusya_diy"

HOST: Final = "https://vc.go.mail.ru"
VK_APP_ID: Final = "6463690"
VK_LOGIN_URL: Final = (
    f"https://oauth.vk.com/authorize?client_id={VK_APP_ID}"
    "&redirect_uri=https://oauth.vk.com/blank.html&response_type=token&display=page&v=5.131"
)
APP_VERSION: Final = "1.91.5"

KIND: Final = "kind"
KIND_ACCOUNT: Final = "account"
KIND_CABINET: Final = "cabinet"
CABINET_UNIQUE_ID: Final = "cabinet"

CONF_DEVICE_ID: Final = "device_id"
CONF_SESSION_ID: Final = "session_id"
CONF_SESSION_SECRET: Final = "session_secret"
CONF_ACCOUNT_ID: Final = "account_id"
CONF_VK_USER_ID: Final = "vk_user_id"
CONF_SH_DATA: Final = "sh_data"
CONF_SH_DATA_SET: Final = "sh_data_set"
CONF_HOOK_TOKEN: Final = "hook_token"
CONF_HOOK_REFRESH_TOKEN_ID: Final = "hook_refresh_token_id"
CONF_HOOK_USER_ID: Final = "hook_user_id"
CONF_CONFIG_ID: Final = "config_id"
CONF_CONFIG_NAME: Final = "config_name"
CONF_CONFIG_FINGERPRINT: Final = "config_fingerprint"

OPT_DEFAULT_ROOM: Final = "default_room"
OPT_DEVICES: Final = "devices"
OPT_BASE_URL: Final = "base_url"
