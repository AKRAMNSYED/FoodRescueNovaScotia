(() => {
    const app = document.getElementById('mp-app');
    if (!app) return;

    const authPanel = document.getElementById('mp-auth');
    const authForm = document.getElementById('mp-auth-form');
    const authTitle = document.getElementById('mp-auth-title');
    const authSwitch = document.getElementById('mp-auth-switch');
    const authSwitchLabel = document.getElementById('mp-auth-switch-label');
    const authSubmit = document.getElementById('mp-auth-submit');
    const authError = document.getElementById('mp-auth-error');
    const avatarSelect = document.getElementById('mp-avatar');
    const avatarLabel = document.getElementById('mp-avatar-label');
    const world = document.getElementById('mp-world');
    const canvas = document.getElementById('mp-canvas');
    const ctx = canvas.getContext('2d');
    const status = document.getElementById('mp-game-status');
    const phaseEl = document.getElementById('mp-phase');
    const balanceEl = document.getElementById('mp-balance');
    const heldEl = document.getElementById('mp-cans-held');
    const donatedEl = document.getElementById('mp-total-cans');
    const ballsEl = document.getElementById('mp-soccer-balls');
    const playerLabel = document.getElementById('mp-player-label');
    const actionButton = document.getElementById('mp-action');
    const bingoSection = document.getElementById('mp-bingo');
    const bingoTitle = document.getElementById('mp-bingo-title');
    const bingoBoard = document.getElementById('mp-bingo-board');
    const bingoCallEl = document.getElementById('mp-bingo-call');
    const bingoTimeEl = document.getElementById('mp-bingo-round-time');
    const bingoMessage = document.getElementById('mp-bingo-message');
    const bingoClaim = document.getElementById('mp-bingo-claim');
    const bingoWinners = document.getElementById('mp-bingo-winners');
    const leaderboardDialog = document.getElementById('mp-leaderboard');
    const leaderboardList = document.getElementById('mp-leaderboard-list');

    const config = app.dataset;
    const assetsRoot = document.getElementById('mp-assets');
    const asset = (key) => {
        const image = new Image();
        image.src = assetsRoot.dataset[key];
        return image;
    };
    const pictures = {
        eve: asset('eve'),
        eveWalk: asset('eveWalk'),
        jim: asset('jim'),
        jimWalk: asset('jimWalk'),
        hatStand: asset('hatStand'),
        hatWalk: asset('hatWalk'),
        sobeys: asset('sobeys'),
        feed: asset('feed'),
        aj: asset('aj'),
        houses: ['house1', 'house2', 'house3', 'house4'].map(asset),
        trees: ['tree1', 'tree2', 'tree3'].map(asset),
        sun: asset('sun'),
        moon: asset('moon'),
    };

    const API = {
        auth: config.authUrl,
        session: config.sessionUrl,
        logout: config.logoutUrl,
        leaderboard: config.leaderboardUrl,
    };
    const WORLD_WIDTH = 960;
    const STORE_X = 450;
    const FEED_X = -450;
    const BINGO_X = 1050;
    const PLAYER_SPEED = 220;
    const pressed = new Set();
    const remotePlayers = new Map();
    let player = null;
    let socket = null;
    let reconnectTimer = null;
    let reconnectDelay = 1000;
    let localX = 0;
    let phase = 'day';
    let phaseSecondsLeft = 0;
    let roundNumber = null;
    let bingo = null;
    let bingoMarks = new Set();
    let renderedBingoRound = null;
    let lastSnapshotAt = performance.now();
    let lastMoveSentAt = 0;
    let lastSyncAt = 0;
    let animationId = 0;
    let previousFrame = performance.now();
    let clockAdjustment = 0;
    let actionPending = false;
    let authMode = 'login';
    let currentStatus = '';
    const customizer = document.getElementById('mp-customizer');
    const customPreview = document.getElementById('mp-custom-preview');
    const customInputs = {
        hair: document.getElementById('mp-custom-hair'),
        hairColor: document.getElementById('mp-custom-hair-color'),
        skin: document.getElementById('mp-custom-skin'),
        shirt: document.getElementById('mp-custom-shirt'),
        pants: document.getElementById('mp-custom-pants'),
        shoes: document.getElementById('mp-custom-shoes'),
        shoulders: document.getElementById('mp-custom-shoulders'),
        hat: document.getElementById('mp-custom-hat'),
        hatColor: document.getElementById('mp-custom-hat-color'),
    };
    const customDefaults = {
        hair: 'long',
        hairColor: '#ffeb3b',
        skin: '#ffecb3',
        shirt: '#8bc34a',
        pants: '#0288d1',
        shoes: '#f44336',
        shoulders: 0,
        hat: false,
        hatColor: '#689f38',
    };
    const customSpriteCache = new Map();

    const csrfToken = () => {
        const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    };

    const readCustomCharacter = () => ({
        hair: customInputs.hair.value,
        hairColor: customInputs.hairColor.value,
        skin: customInputs.skin.value,
        shirt: customInputs.shirt.value,
        pants: customInputs.pants.value,
        shoes: customInputs.shoes.value,
        shoulders: Number(customInputs.shoulders.value),
        hat: customInputs.hat.checked,
        hatColor: customInputs.hatColor.value,
    });

    const applyCustomCharacter = (settings) => {
        const values = { ...customDefaults, ...(settings || {}) };
        Object.entries(customInputs).forEach(([key, input]) => {
            if (key === 'hat') input.checked = Boolean(values[key]);
            else input.value = values[key];
        });
        customSpriteCache.clear();
        drawCustomPreview();
    };

    const tintSprite = (image, settings, hatImage) => {
        if (!image?.complete || !image.naturalWidth) return image;
        const source = document.createElement('canvas');
        source.width = image.naturalWidth;
        source.height = image.naturalHeight;
        const sourceContext = source.getContext('2d', { willReadFrequently: true });
        sourceContext.drawImage(image, 0, 0);
        const frame = sourceContext.getImageData(0, 0, source.width, source.height);
        const pixels = frame.data;
        const targets = {
            hair: settings.hairColor,
            skin: settings.skin,
            shirt: settings.shirt,
            pants: settings.pants,
            shoes: settings.shoes,
        };
        const references = {
            hair: [255, 235, 59],
            skin: [255, 236, 179],
            shirt: [139, 195, 74],
            pants: [2, 136, 209],
            shoes: [244, 67, 54],
        };
        const targetRgb = (value) => [1, 3, 5].map((index) => parseInt(value.slice(index, index + 2), 16));
        const luminance = (r, g, b) => .299 * r + .587 * g + .114 * b;
        const regionOf = (r, g, b) => {
            if (r > 235 && g > 170 && b < 135) return 'hair';
            if (r > 235 && g > 195 && g < 246 && b >= 140 && b < 200) return 'skin';
            if (g > r + 25 && g > b + 40 && r < 170) return 'shirt';
            if (b > r + 100 && b > g + 30) return 'pants';
            if (r > 150 && g < 100 && b < 100) return 'shoes';
            return null;
        };
        const topY = (() => {
            for (let y = 0; y < source.height; y += 1) {
                for (let x = 0; x < source.width; x += 1) {
                    if (pixels[(y * source.width + x) * 4 + 3]) return y;
                }
            }
            return 0;
        })();
        const hairCutoff = topY + source.height * .17;

        for (let y = 0; y < source.height; y += 1) {
            for (let x = 0; x < source.width; x += 1) {
                const index = (y * source.width + x) * 4;
                if (!pixels[index + 3]) continue;
                const region = regionOf(pixels[index], pixels[index + 1], pixels[index + 2]);
                if (!region || (region === 'hair' && settings.hair === 'short' && y > hairCutoff)) continue;
                const target = targetRgb(targets[region]);
                const reference = references[region];
                const sourceLuminance = luminance(pixels[index], pixels[index + 1], pixels[index + 2]);
                const referenceLuminance = luminance(...reference);
                const ratio = sourceLuminance / referenceLuminance;
                for (let channel = 0; channel < 3; channel += 1) {
                    const value = ratio <= 1
                        ? target[channel] * ratio
                        : target[channel] + (255 - target[channel]) * Math.min(1, ratio - 1);
                    pixels[index + channel] = Math.max(0, Math.min(255, value));
                }
            }
        }
        sourceContext.putImageData(frame, 0, 0);

        const widen = Number(settings.shoulders) * 3;
        const result = document.createElement('canvas');
        result.width = source.width + widen * 2;
        result.height = source.height;
        const context = result.getContext('2d');
        context.imageSmoothingEnabled = false;
        context.drawImage(source, widen, 0);
        if (widen) {
            context.drawImage(source, 0, Math.floor(source.height * .26), Math.floor(source.width * .28), Math.floor(source.height * .37),
                0, Math.floor(source.height * .26), Math.floor(source.width * .28), Math.floor(source.height * .37));
            context.drawImage(source, Math.floor(source.width * .72), Math.floor(source.height * .26), Math.floor(source.width * .28), Math.floor(source.height * .37),
                result.width - Math.floor(source.width * .28), Math.floor(source.height * .26), Math.floor(source.width * .28), Math.floor(source.height * .37));
        }
        if (settings.hat && hatImage?.complete && hatImage.naturalWidth) {
            const hat = document.createElement('canvas');
            hat.width = hatImage.naturalWidth;
            hat.height = hatImage.naturalHeight;
            const hatContext = hat.getContext('2d', { willReadFrequently: true });
            hatContext.drawImage(hatImage, 0, 0);
            const hatPixels = hatContext.getImageData(0, 0, hat.width, hat.height);
            const target = targetRgb(settings.hatColor);
            for (let index = 0; index < hatPixels.data.length; index += 4) {
                const data = hatPixels.data;
                if (!data[index + 3] || luminance(data[index], data[index + 1], data[index + 2]) < 40) continue;
                const ratio = luminance(data[index], data[index + 1], data[index + 2]) / luminance(104, 159, 56);
                for (let channel = 0; channel < 3; channel += 1) {
                    data[index + channel] = Math.max(0, Math.min(255, target[channel] * ratio));
                }
            }
            hatContext.putImageData(hatPixels, 0, 0);
            const hatTop = Math.max(0, Math.round(topY - hat.height + 10));
            context.drawImage(hat, Math.round(result.width / 2 - hat.width / 2), hatTop);
        }
        return result;
    };

    const characterSprite = (person, walking = false) => {
        if (person.avatar !== 'custom') {
            return pictures[person.avatar === 'jim' ? (walking ? 'jimWalk' : 'jim') : (walking ? 'eveWalk' : 'eve')];
        }
        const settings = { ...customDefaults, ...(person.custom_character || {}) };
        const key = JSON.stringify([person.id, walking, settings]);
        if (!customSpriteCache.has(key)) {
            customSpriteCache.set(key, tintSprite(
                walking ? pictures.eveWalk : pictures.eve,
                settings,
                walking ? pictures.hatWalk : pictures.hatStand,
            ));
        }
        return customSpriteCache.get(key);
    };

    const drawCustomPreview = () => {
        if (!customPreview || !pictures.eve?.complete || !pictures.eve.naturalWidth) return;
        const settings = readCustomCharacter();
        const standing = tintSprite(pictures.eve, settings, pictures.hatStand);
        const walking = tintSprite(pictures.eveWalk, settings, pictures.hatWalk);
        const context = customPreview.getContext('2d');
        context.clearRect(0, 0, customPreview.width, customPreview.height);
        context.imageSmoothingEnabled = false;
        [standing, walking].forEach((sprite, index) => {
            if (!sprite?.width || !sprite?.height) return;
            const scale = Math.min(150 / sprite.height, 170 / sprite.width);
            const width = sprite.width * scale;
            const height = sprite.height * scale;
            context.drawImage(sprite, index * 180 + (180 - width) / 2, 170 - height, width, height);
            context.fillStyle = '#0b3d2e';
            context.textAlign = 'center';
            context.font = '12px Comfortaa, Arial, sans-serif';
            context.fillText(index ? 'Walking' : 'Standing', index * 180 + 90, 177);
        });
    };

    pictures.eve.addEventListener('load', drawCustomPreview);

    const updateCustomizerVisibility = () => {
        customizer.hidden = authMode !== 'register' || avatarSelect.value !== 'custom';
        if (!customizer.hidden) drawCustomPreview();
    };

    avatarSelect.addEventListener('change', updateCustomizerVisibility);
    Object.values(customInputs).forEach((input) => {
        input.addEventListener('input', () => {
            customSpriteCache.clear();
            drawCustomPreview();
        });
        input.addEventListener('change', () => {
            customSpriteCache.clear();
            drawCustomPreview();
        });
    });

    const setStatus = (message) => {
        currentStatus = message || '';
        status.textContent = currentStatus;
    };

    const send = (payload) => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(payload));
            return true;
        }
        return false;
    };

    const showAuth = (message = '') => {
        world.hidden = true;
        authPanel.hidden = false;
        authError.textContent = message;
        document.getElementById('mp-password').value = '';
    };

    const showWorld = () => {
        authPanel.hidden = true;
        world.hidden = false;
    };

    const setAuthMode = (mode) => {
        authMode = mode;
        const registering = mode === 'register';
        authTitle.textContent = registering ? 'Create a multiplayer account' : 'Sign in to multiplayer';
        authSubmit.textContent = registering ? 'Create account' : 'Sign in';
        authSwitchLabel.textContent = registering ? 'Already have an account?' : 'New player?';
        authSwitch.textContent = registering ? 'Sign in' : 'Create an account';
        document.getElementById('mp-password').autocomplete = registering ? 'new-password' : 'current-password';
        avatarSelect.hidden = !registering;
        avatarLabel.hidden = !registering;
        updateCustomizerVisibility();
        authError.textContent = '';
    };

    authSwitch.addEventListener('click', () => {
        setAuthMode(authMode === 'login' ? 'register' : 'login');
    });

    authForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        authError.textContent = '';
        authSubmit.disabled = true;
        try {
            const response = await fetch(API.auth, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
                body: JSON.stringify({
                    mode: authMode,
                    name: document.getElementById('mp-name').value,
                    password: document.getElementById('mp-password').value,
                    avatar: avatarSelect.value,
                    custom_character: readCustomCharacter(),
                }),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Could not sign in.');
            player = result.player;
            localX = 0;
            setStatus('Welcome, ' + player.name + '. Loading the multiplayer world…');
            connect();
        } catch (error) {
            authError.textContent = error.message || 'Could not connect. Please try again.';
        } finally {
            authSubmit.disabled = false;
        }
    });

    const updateHud = () => {
        if (!player) return;
        playerLabel.textContent = player.name;
        balanceEl.textContent = '$' + player.balance;
        heldEl.textContent = player.cans_held + (player.cans_held === 1 ? ' can' : ' cans');
        donatedEl.textContent = player.donated_cans + ' donated';
        ballsEl.textContent = player.soccer_balls + (player.soccer_balls === 1 ? ' soccer ball' : ' soccer balls');
    };

    const setPlayer = (updated) => {
        if (!updated || !player || updated.id !== player.id) return;
        player = { ...player, ...updated };
        updateHud();
        for (const [id, remote] of remotePlayers) {
            if (id === player.id) remote.donated_cans = player.donated_cans;
        }
    };

    const updatePresence = (presence) => {
        if (!presence || !Number.isFinite(Number(presence.x))) return;
        if (player && presence.id === player.id) {
            localX = Number(presence.x);
            return;
        }
        const old = remotePlayers.get(presence.id);
        const x = Number(presence.x);
        remotePlayers.set(presence.id, {
            ...old,
            ...presence,
            x,
            walking: Boolean(old && Math.abs(old.x - x) > 0.5),
            lastMovedAt: performance.now(),
        });
    };

    const applySnapshot = (data) => {
        if (data.player) setPlayer(data.player);
        for (const online of data.online_players || []) updatePresence(online);
        const activeIds = new Set((data.online_players || []).map((online) => online.id));
        if (player) activeIds.add(player.id);
        for (const id of remotePlayers.keys()) {
            if (!activeIds.has(id)) remotePlayers.delete(id);
        }
        phase = data.phase || phase;
        phaseSecondsLeft = Number(data.phase_seconds_left) || 0;
        roundNumber = data.round_number;
        bingo = data.bingo;
        if (bingo && bingo.round_number !== renderedBingoRound) {
            renderedBingoRound = bingo.round_number;
            bingoMarks = new Set(['FREE']);
            bingoMessage.textContent = '';
        }
        if (!bingo) renderedBingoRound = null;
        clockAdjustment = 0;
        lastSnapshotAt = performance.now();
        updateBingo();
        updateHud();
    };

    const connect = () => {
        if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
        clearTimeout(reconnectTimer);
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(protocol + '//' + window.location.host + config.wsPath);
        socket.addEventListener('open', () => {
            reconnectDelay = 1000;
            showWorld();
            send({ type: 'sync' });
            setStatus('Connected. Donate cans to climb the leaderboard.');
        });
        socket.addEventListener('message', (event) => {
            let data;
            try {
                data = JSON.parse(event.data);
            } catch {
                return;
            }
            if (data.type === 'snapshot') {
                applySnapshot(data);
            } else if (data.type === 'presence_joined' || data.type === 'player_moved') {
                updatePresence(data.player);
            } else if (data.type === 'presence_left') {
                remotePlayers.delete(data.player_id);
            } else if (data.type === 'player_changed') {
                setPlayer(data.player);
                const remote = remotePlayers.get(data.player.id);
                if (remote) remote.donated_cans = data.player.donated_cans;
            } else if (data.type === 'action_result') {
                actionPending = false;
                actionButton.disabled = false;
                setStatus(data.message);
                if (data.ok) setPlayer(data.player);
                updateActionButton();
            } else if (data.type === 'bingo_result') {
                bingoClaim.disabled = false;
                bingoMessage.textContent = data.message;
                if (data.ok) {
                    if (data.player) setPlayer(data.player);
                    send({ type: 'sync' });
                }
            } else if (data.type === 'bingo_winner') {
                bingoMessage.textContent = data.message;
                send({ type: 'sync' });
            }
        });
        socket.addEventListener('close', (event) => {
            if (event.code === 4401) {
                player = null;
                showAuth('Please sign in again to continue.');
                return;
            }
            if (player) {
                setStatus('Connection interrupted. Reconnecting…');
                reconnectTimer = setTimeout(connect, reconnectDelay);
                reconnectDelay = Math.min(15000, reconnectDelay * 2);
            }
        });
        socket.addEventListener('error', () => {
            setStatus('Could not connect to multiplayer. Check the server setup and try again.');
        });
    };

    const currentWorldX = () => player ? localX : 0;
    const nearestLocation = () => {
        const x = currentWorldX();
        const storeDistance = Math.abs(x - STORE_X);
        const feedDistance = Math.abs(x - FEED_X);
        if (storeDistance <= 105 && storeDistance <= feedDistance) return 'buy';
        if (feedDistance <= 105) return 'donate';
        return null;
    };

    const updateActionButton = () => {
        const action = nearestLocation();
        const allowed = phase === 'day' && action && !actionPending && socket?.readyState === WebSocket.OPEN;
        actionButton.disabled = !allowed;
        actionButton.textContent = action === 'buy' ? 'Buy can ($5)' : action === 'donate' ? 'Donate 1 can' : 'Interact';
    };

    const performAction = () => {
        const action = nearestLocation();
        if (!action || phase !== 'day' || actionPending) return;
        actionPending = true;
        actionButton.disabled = true;
        send({ type: 'action', action });
    };

    actionButton.addEventListener('click', performAction);
    document.addEventListener('keydown', (event) => {
        if (event.target instanceof HTMLElement && /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
        const key = event.key.toLowerCase();
        if (key === 'e') {
            event.preventDefault();
            performAction();
        }
        if (['arrowleft', 'a', 'arrowright', 'd'].includes(key)) {
            event.preventDefault();
            pressed.add(key === 'arrowleft' || key === 'a' ? 'left' : 'right');
        }
    });
    document.addEventListener('keyup', (event) => {
        const key = event.key.toLowerCase();
        if (key === 'arrowleft' || key === 'a') pressed.delete('left');
        if (key === 'arrowright' || key === 'd') pressed.delete('right');
    });
    window.addEventListener('blur', () => pressed.clear());
    document.querySelectorAll('[data-move]').forEach((button) => {
        const direction = Number(button.dataset.move) < 0 ? 'left' : 'right';
        const start = (event) => {
            event.preventDefault();
            pressed.add(direction);
            button.setPointerCapture?.(event.pointerId);
        };
        const stop = () => pressed.delete(direction);
        button.addEventListener('pointerdown', start);
        button.addEventListener('pointerup', stop);
        button.addEventListener('pointercancel', stop);
        button.addEventListener('lostpointercapture', stop);
    });

    const drawBuilding = (image, worldX, label, cameraX, night) => {
        if (!image.complete || !image.naturalWidth) return;
        const scale = Math.min(1, 150 / image.naturalWidth);
        const width = image.naturalWidth * scale;
        const height = image.naturalHeight * scale;
        const x = WORLD_WIDTH / 2 + worldX - cameraX - width / 2;
        const y = 340 - height;
        ctx.drawImage(image, x, y, width, height);
        ctx.fillStyle = night ? '#fff' : '#173b2c';
        ctx.font = 'bold 16px Comfortaa, Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(label, x + width / 2, y - 8);
    };

    const drawPlayer = (person, cameraX, isLocal, crowned) => {
        const x = WORLD_WIDTH / 2 + person.x - cameraX;
        if (x < -55 || x > WORLD_WIDTH + 55) return;
        const moving = isLocal ? pressed.size > 0 : person.walking && performance.now() - person.lastMovedAt < 350;
        const image = characterSprite(person, moving);
        const imageWidth = image.naturalWidth || image.width;
        const imageHeight = image.naturalHeight || image.height;
        const h = imageWidth && imageHeight ? 90 : 70;
        const w = imageWidth && imageHeight ? h * imageWidth / imageHeight : 48;
        const y = 420;
        if (imageWidth && imageHeight) {
            ctx.drawImage(image, x - w / 2, y - h, w, h);
        } else {
            ctx.fillStyle = isLocal ? '#f59e0b' : '#2563eb';
            ctx.fillRect(x - 15, y - h, 30, h);
        }
        ctx.textAlign = 'center';
        ctx.font = 'bold 13px Comfortaa, Arial, sans-serif';
        ctx.lineWidth = 4;
        ctx.strokeStyle = '#fff';
        ctx.strokeText((person.donated_cans || 0) + ' cans', x, y - h - 25);
        ctx.fillStyle = '#0b3d2e';
        ctx.fillText((person.donated_cans || 0) + ' cans', x, y - h - 25);
        if (crowned) {
            ctx.font = '24px Arial, sans-serif';
            ctx.fillText('👑', x, y - h - 42);
        }
        ctx.font = 'bold 13px Comfortaa, Arial, sans-serif';
        ctx.lineWidth = 4;
        ctx.strokeStyle = '#fff';
        ctx.strokeText(person.name, x, y - h - 7);
        ctx.fillStyle = isLocal ? '#8a3d08' : '#172554';
        ctx.fillText(person.name, x, y - h - 7);
    };

    const drawWorld = () => {
        const cameraX = localX;
        const isNight = phase === 'night';
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const sky = ctx.createLinearGradient(0, 0, 0, 330);
        sky.addColorStop(0, isNight ? '#102244' : '#56c8f2');
        sky.addColorStop(1, isNight ? '#29385b' : '#d8f3ff');
        ctx.fillStyle = sky;
        ctx.fillRect(0, 0, canvas.width, 330);
        ctx.fillStyle = isNight ? '#243b35' : '#75bb57';
        ctx.fillRect(0, 330, canvas.width, 218);
        if (isNight) {
            ctx.fillStyle = 'rgba(7, 14, 39, .38)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
        }

        drawBuilding(pictures.sobeys, STORE_X, 'Sobeys', cameraX, isNight);
        drawBuilding(pictures.feed, FEED_X, 'Feed Nova Scotia', cameraX, isNight);
        drawBuilding(pictures.aj, BINGO_X, 'A.J. Smeltzer', cameraX, isNight);

        ctx.fillStyle = '#4b4d51';
        ctx.fillRect(0, 340, canvas.width, 140);
        ctx.fillStyle = '#f6d35c';
        for (let x = -((cameraX % 80) + 80) % 80; x < canvas.width; x += 80) {
            ctx.fillRect(x, 408, 42, 5);
        }

        pictures.houses.forEach((house, index) => {
            if (!house.complete || !house.naturalWidth) return;
            const worldX = -1200 + index * 190;
            const x = canvas.width / 2 + worldX - cameraX;
            if (x > -120 && x < canvas.width + 120) {
                const h = 85;
                const w = h * house.naturalWidth / house.naturalHeight;
                ctx.drawImage(house, x - w / 2, 340 - h, w, h);
            }
        });
        const active = [...remotePlayers.values()].filter((item) => item.id !== player?.id);
        const local = { ...player, x: localX };
        const crownTarget = [...active, local].sort((a, b) =>
            (b.donated_cans || 0) - (a.donated_cans || 0) || String(a.name).localeCompare(String(b.name))
        )[0];
        active.forEach((person) => drawPlayer(person, cameraX, false, crownTarget?.id === person.id));
        drawPlayer(local, cameraX, true, crownTarget?.id === player?.id);
        pictures.trees.forEach((tree, index) => {
            if (!tree.complete || !tree.naturalWidth) return;
            const worldX = 800 + index * 260;
            const x = canvas.width / 2 + worldX - cameraX;
            if (x > -100 && x < canvas.width + 100) {
                const h = 100;
                const w = h * tree.naturalWidth / tree.naturalHeight;
                ctx.drawImage(tree, x - w / 2, 295 - h, w, h);
            }
        });
        if (!isNight && pictures.sun.complete && pictures.sun.naturalWidth) {
            ctx.drawImage(pictures.sun, 800, 28, 72, 72);
        } else if (isNight && pictures.moon.complete && pictures.moon.naturalWidth) {
            ctx.drawImage(pictures.moon, 800, 28, 72, 72);
        }
    };

    const renderBingo = () => {
        bingoBoard.textContent = '';
        if (!bingo) return;
        const called = new Set(bingo.calls || []);
        bingo.card.forEach((row, rowIndex) => row.forEach((value, columnIndex) => {
            const cell = document.createElement('button');
            cell.type = 'button';
            cell.className = 'mp-bingo-cell';
            const isFree = value === 'FREE';
            const isCalled = isFree || called.has(value);
            const key = rowIndex + ':' + columnIndex;
            if (isCalled) cell.classList.add('called');
            if (bingoMarks.has(key)) cell.classList.add('marked');
            cell.textContent = isFree ? 'FREE' : String(value);
            cell.disabled = !isCalled;
            cell.setAttribute('aria-pressed', String(bingoMarks.has(key)));
            cell.addEventListener('click', () => {
                bingoMarks.add(key);
                cell.classList.add('marked');
                cell.setAttribute('aria-pressed', 'true');
                updateBingoClaim();
            });
            bingoBoard.appendChild(cell);
        }));
        const latest = bingo.calls?.length ? bingo.calls[bingo.calls.length - 1] : null;
        bingoCallEl.textContent = latest
            ? 'Latest call: ' + 'BINGO'[Math.min(4, Math.floor((latest - 1) / 15))] + ' ' + latest
            : 'Waiting for the first number…';
        bingoTimeEl.textContent = bingo.calls?.length
            ? 'Called numbers: ' + bingo.calls.join(', ')
            : 'Numbers will start shortly.';
        bingoWinners.textContent = '';
        (bingo.winners || []).forEach((winner) => {
            const item = document.createElement('li');
            item.textContent = winner.name + ' 👑';
            bingoWinners.appendChild(item);
        });
        for (let index = (bingo.winners || []).length; index < 3; index += 1) {
            const item = document.createElement('li');
            item.textContent = 'Winner spot open';
            bingoWinners.appendChild(item);
        }
        updateBingoClaim();
    };

    const updateBingoClaim = () => {
        if (!bingo || !player) {
            bingoClaim.disabled = true;
            return;
        }
        const diagonal = [0, 1, 3, 4].every((index) => bingoMarks.has(index + ':' + index));
        const alreadyWon = (bingo.winners || []).some((winner) => winner.id === player.id);
        bingoClaim.disabled = !diagonal || alreadyWon || (bingo.winners || []).length >= 3;
    };

    const updateBingo = () => {
        bingoSection.hidden = !(phase === 'night' && bingo);
        if (bingoSection.hidden) return;
        bingoTitle.textContent = 'Bingo night — round ' + bingo.round_number + ' of 3';
        renderBingo();
    };

    bingoClaim.addEventListener('click', () => {
        if (!bingo || bingoClaim.disabled) return;
        bingoClaim.disabled = true;
        bingoMessage.textContent = 'Checking your bingo…';
        send({ type: 'claim_bingo', round_number: bingo.round_number });
    });

    const updateLeaderboard = async () => {
        leaderboardList.textContent = 'Loading…';
        leaderboardDialog.hidden = false;
        try {
            const response = await fetch(API.leaderboard);
            if (!response.ok) throw new Error('Leaderboard is not available.');
            const data = await response.json();
            leaderboardList.textContent = '';
            if (!data.players.length) {
                leaderboardList.textContent = 'No donations have been recorded yet.';
                return;
            }
            data.players.forEach((entry) => {
                const item = document.createElement('li');
                item.className = 'mp-leaderboard-row';
                const rank = document.createElement('span');
                const name = document.createElement('strong');
                const total = document.createElement('span');
                rank.textContent = String(entry.rank) + '.';
                name.textContent = entry.name;
                total.textContent = String(entry.donated_cans) + (entry.donated_cans === 1 ? ' can' : ' cans');
                item.append(rank, name, total);
                leaderboardList.appendChild(item);
            });
        } catch (error) {
            leaderboardList.textContent = error.message;
        }
    };

    document.getElementById('mp-leaderboard-open').addEventListener('click', updateLeaderboard);
    document.getElementById('mp-leaderboard-close').addEventListener('click', () => {
        leaderboardDialog.hidden = true;
    });
    leaderboardDialog.addEventListener('click', (event) => {
        if (event.target === leaderboardDialog) leaderboardDialog.hidden = true;
    });

    document.getElementById('mp-logout').addEventListener('click', async () => {
        try {
            await fetch(API.logout, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken() },
            });
        } finally {
            if (socket) socket.close();
            clearTimeout(reconnectTimer);
            player = null;
            remotePlayers.clear();
            showAuth();
            setAuthMode('login');
            setStatus('');
        }
    });

    if (config.enabled !== 'true') return;

    const frame = (now) => {
        const dt = Math.min(.05, Math.max(0, (now - previousFrame) / 1000));
        previousFrame = now;
        if (player && socket?.readyState === WebSocket.OPEN) {
            const direction = Number(pressed.has('right')) - Number(pressed.has('left'));
            if (direction) localX = Math.max(-2500, Math.min(2500, localX + direction * PLAYER_SPEED * dt));
            if (now - lastMoveSentAt >= 250) {
                send({ type: 'move', x: localX });
                lastMoveSentAt = now;
            }
            if (now - lastSyncAt >= 2500) {
                send({ type: 'sync' });
                lastSyncAt = now;
            }
            const elapsed = Math.floor((now - lastSnapshotAt) / 1000);
            const remaining = Math.max(0, phaseSecondsLeft - elapsed + clockAdjustment);
            const mins = Math.floor(remaining / 60);
            const secs = String(remaining % 60).padStart(2, '0');
            phaseEl.textContent = (phase === 'day' ? '☀️ Day' : '🌙 Night') + ' — ' + mins + ':' + secs +
                (phase === 'night' && roundNumber ? ' · Bingo round ' + roundNumber + '/3' : '');
            if (bingo) {
                const left = Math.max(0, bingo.round_seconds_left - elapsed);
                bingoTimeEl.textContent = 'Round ' + bingo.round_number + ' ends in ' + Math.floor(left / 60) +
                    ':' + String(left % 60).padStart(2, '0') + '\n' +
                    (bingo.calls?.length ? 'Called: ' + bingo.calls.join(', ') : 'Numbers will start shortly.');
            }
            updateActionButton();
        }
        drawWorld();
        animationId = requestAnimationFrame(frame);
    };
    animationId = requestAnimationFrame(frame);

    fetch(API.session)
        .then(async (response) => {
            if (!response.ok) {
                if (response.status !== 401) {
                    const data = await response.json();
                    throw new Error(data.error || 'Multiplayer is unavailable.');
                }
                showAuth();
                return null;
            }
            return response.json();
        })
        .then((data) => {
            if (!data || !data.player) {
                showAuth();
                return;
            }
            player = data.player;
            localX = 0;
            connect();
        })
        .catch((error) => {
            showAuth(error.message || 'Multiplayer is unavailable.');
        });

    window.addEventListener('pagehide', () => {
        cancelAnimationFrame(animationId);
        if (socket) socket.close();
    });
})();
