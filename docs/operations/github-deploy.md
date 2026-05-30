# Git deploy на production (SSH deploy key)

## Быстрая настройка на сервере

```bash
/root/veil-xray/scripts/ops/setup-github-deploy-ssh.sh
```

Скрипт:

- создаёт `~/.ssh/id_ed25519_veil_xray_deploy` (если нет);
- добавляет блок `Host github.com` в `~/.ssh/config`;
- переключает `origin` на `git@github.com:merdocx/veil-xray.git`;
- удаляет лишний remote `veilbot`.

## Регистрация ключа в GitHub (один раз)

1. Откройте https://github.com/merdocx/veil-xray/settings/keys
2. **Add deploy key** → вставьте содержимое `~/.ssh/id_ed25519_veil_xray_deploy.pub`
3. Title: `veil-xray-prod-<hostname>`
4. **Read-only** (без write access)

## Проверка

```bash
cd /root/veil-xray
git fetch origin main
git status -sb
```

## HTTPS + PAT (альтернатива deploy key)

Учётные данные хранятся **вне репозитория**: `/root/.config/git/veil-xray.credentials` (`chmod 600`).  
Не коммитьте PAT и не кладите токен в `.env` проекта.

```bash
cd /root/veil-xray
/root/veil-xray/scripts/ops/git-with-credentials.sh pull --ff-only origin main
# или любая git-команда:
# /root/veil-xray/scripts/ops/git-with-credentials.sh fetch origin main
```

`origin` должен быть `https://github.com/merdocx/veil-xray.git`.

## Обновление кода на prod

```bash
cd /root/veil-xray
/root/veil-xray/scripts/ops/git-with-credentials.sh pull --ff-only origin main
/root/veil-xray/scripts/ops/deploy-prod.sh
# deploy-prod: git pull в /root/veil-xray → rsync в /opt/veil-xray → restart API
```

`deploy-prod.sh` применяет sysctl, cron, **policy recommended** (если отличается от эталона), перезапускает API.  
После смены только `config.json` на хосте вручную: `xray -test` и `systemctl restart xray`.

Рекомендуемые значения: [RECOMMENDED_SETTINGS.md](RECOMMENDED_SETTINGS.md).

## Troubleshooting

| Симптом | Действие |
|---------|----------|
| `Permission denied (publickey)` | Ключ не добавлен в Deploy keys или неверный репозиторий |
| `Host key verification failed` | Повторить `ssh-keyscan github.com >> ~/.ssh/known_hosts` |
| HTTPS remote вместо SSH | `git remote set-url origin git@github.com:merdocx/veil-xray.git` |

Публичный ключ **не хранится в репозитории** — только на сервере в `~/.ssh/id_ed25519_veil_xray_deploy.pub`.
