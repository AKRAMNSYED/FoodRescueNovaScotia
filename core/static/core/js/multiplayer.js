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
        background: asset('background'),
        cloud: asset('cloud'),
        eve: asset('eve'),
        eveWalk: asset('eveWalk'),
        jim: asset('jim'),
        jimWalk: asset('jimWalk'),
        hatStand: asset('hatStand'),
        hatWalk: asset('hatWalk'),
        sobeys: asset('sobeys'),
        feed: asset('feed'),
        aj: asset('aj'),
        trading: asset('trading'),
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
    const TRADING_X = BINGO_X - 100;
    const PLAYER_SPEED = 220;
    const HOUSE_SCALE = 0.715;
    const TREE_HEIGHT = 210;
    const ROAD_TOP_MARGIN = 38;
    const ROAD_BOTTOM_MARGIN = 20;
    const pressed = new Set();
    const remotePlayers = new Map();
    let player = null;
    let crownPlayerId = null;
    let socket = null;
    let reconnectTimer = null;
    let reconnectDelay = 1000;
    let localX = 0;
    let roadMap = null;
    let nightBackground = null;
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

    const PIXEL = 8.6;
    const SHORT_HAIR_CUT = 0.17;
    const HAT_OVERLAP = 0;
    const REGION_REF = {
        hair: [255, 235, 59], skin: [255, 236, 179], shirt: [139, 195, 74],
        pants: [2, 136, 209], shoes: [244, 67, 54],
    };
    const hexToRgb = (hex) => [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16));
    const lum = (red, green, blue) => 0.299 * red + 0.587 * green + 0.114 * blue;
    const regionOf = (red, green, blue) => {
        if (red > 235 && green > 170 && blue < 135) return 'hair';
        if (red > 235 && green > 195 && green < 246 && blue >= 140 && blue < 200) return 'skin';
        if (green > red + 25 && green > blue + 40 && red < 170) return 'shirt';
        if (blue > red + 100 && blue > green + 30) return 'pants';
        if (red > 150 && green < 100 && blue < 100) return 'shoes';
        return '';
    };
    const tint = (target, reference, red, green, blue) => {
        const ratio = lum(red, green, blue) / lum(...reference);
        return target.map((value) => Math.max(
            0,
            Math.min(255, ratio <= 1 ? value * ratio : value + (255 - value) * Math.min(1, ratio - 1)),
        ));
    };
    const normalised = (red, green, blue) => {
        const max = Math.max(red, green, blue) || 1;
        return [red * 255 / max, green * 255 / max, blue * 255 / max];
    };
    const REGION_DIR = Object.fromEntries(
        Object.entries(REGION_REF).map(([name, reference]) => [name, normalised(...reference)]),
    );
    const nearestRegion = (red, green, blue, lowDown) => {
        if (lum(red, green, blue) < 40 || (red > 100 && red < 165 && green > 35 && green < 95 && blue < 65)) return '';
        const direction = normalised(red, green, blue);
        let best = '';
        let bestDistance = 45;
        Object.entries(REGION_DIR).forEach(([name, reference]) => {
            if (name === 'shoes' && !lowDown) return;
            const distance = Math.hypot(
                direction[0] - reference[0],
                direction[1] - reference[1],
                direction[2] - reference[2],
            );
            if (distance < bestDistance) {
                best = name;
                bestDistance = distance;
            }
        });
        return best;
    };
    const isBuckle = (pixels, width, x, y) => {
        const brownAt = (pixelX) => {
            if (pixelX < 0 || pixelX >= width) return false;
            const index = (y * width + pixelX) * 4;
            return pixels[index + 3] > 0 && pixels[index] > 100 && pixels[index] < 165
                && pixels[index + 1] > 35 && pixels[index + 1] < 95 && pixels[index + 2] < 65;
        };
        let left = false;
        let right = false;
        for (let offset = 1; offset <= 28; offset += 1) {
            left = left || brownAt(x - offset);
            right = right || brownAt(x + offset);
        }
        return left && right;
    };

    const tintHat = (hatImage, color) => {
        const canvas = document.createElement('canvas');
        canvas.width = hatImage.width;
        canvas.height = hatImage.height;
        const context = canvas.getContext('2d');
        context.drawImage(hatImage, 0, 0);
        const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
        const pixels = imageData.data;
        const target = hexToRgb(color);
        for (let index = 0; index < pixels.length; index += 4) {
            if (pixels[index + 3] === 0 || lum(pixels[index], pixels[index + 1], pixels[index + 2]) < 40) continue;
            const colorized = tint(target, [104, 159, 56], pixels[index], pixels[index + 1], pixels[index + 2]);
            [pixels[index], pixels[index + 1], pixels[index + 2]] = colorized;
        }
        context.putImageData(imageData, 0, 0);
        return canvas;
    };

    const buildCustomSprite = (image, hatImage, settings) => {
        if (!image?.complete || !image.naturalWidth) return image;
        const width = image.naturalWidth;
        const height = image.naturalHeight;
        const source = document.createElement('canvas');
        source.width = width;
        source.height = height;
        const sourceContext = source.getContext('2d', { willReadFrequently: true });
        sourceContext.drawImage(image, 0, 0);
        const imageData = sourceContext.getImageData(0, 0, width, height);
        const pixels = imageData.data;
        let topY = height;
        let shirtTop = height;
        let pantsTop = height;
        for (let y = 0; y < height; y += 1) {
            for (let x = 0; x < width; x += 1) {
                const index = (y * width + x) * 4;
                if (!pixels[index + 3]) continue;
                topY = Math.min(topY, y);
                const region = regionOf(pixels[index], pixels[index + 1], pixels[index + 2]);
                if (region === 'shirt') shirtTop = Math.min(shirtTop, y);
                if (region === 'pants') pantsTop = Math.min(pantsTop, y);
            }
        }
        const lefts = [];
        const rights = [];
        for (let y = Math.round(shirtTop + (pantsTop - shirtTop) * 0.4); y < pantsTop; y += 1) {
            let left = -1;
            let right = -1;
            for (let x = 0; x < width; x += 1) {
                const index = (y * width + x) * 4;
                if (pixels[index + 3] > 0 && regionOf(pixels[index], pixels[index + 1], pixels[index + 2]) === 'shirt') {
                    if (left < 0) left = x;
                    right = x;
                }
            }
            if (left >= 0) {
                lefts.push(left);
                rights.push(right);
            }
        }
        const median = (values, fallback) => values.length
            ? values.sort((first, second) => first - second)[values.length >> 1]
            : fallback;
        const torsoLeft = median(lefts, 0);
        const torsoRight = median(rights, width - 1);
        const hairLimit = topY + height * 0.45;
        const hairCutoff = topY + height * SHORT_HAIR_CUT;
        for (let y = 0; y < height; y += 1) {
            for (let x = 0; x < width; x += 1) {
                const index = (y * width + x) * 4;
                if (!pixels[index + 3]) continue;
                let region = regionOf(pixels[index], pixels[index + 1], pixels[index + 2]);
                if (!region && Math.min(pixels[index], pixels[index + 1], pixels[index + 2]) > 200) {
                    pixels[index + 3] = 0;
                    continue;
                }
                region = region || nearestRegion(pixels[index], pixels[index + 1], pixels[index + 2], y > height * 0.8);
                if (!region) {
                    if (lum(pixels[index], pixels[index + 1], pixels[index + 2]) > 150) pixels[index + 3] = 0;
                    continue;
                }
                if (region === 'hair' && y > hairLimit && isBuckle(pixels, width, x, y)) continue;
                if (region === 'hair' && settings.hair === 'short' && y > hairCutoff) {
                    pixels[index + 3] = 0;
                    continue;
                }
                const target = hexToRgb(settings[region === 'hair' ? 'hairColor' : region]);
                const colorized = tint(target, REGION_REF[region], pixels[index], pixels[index + 1], pixels[index + 2]);
                [pixels[index], pixels[index + 1], pixels[index + 2]] = colorized;
            }
        }
        for (let index = 0; index < pixels.length; index += 4) {
            pixels[index + 3] = pixels[index + 3] < 128 ? 0 : 255;
        }

        const labels = new Int32Array(width * height);
        let bestLabel = 0;
        let bestSize = 0;
        let nextLabel = 0;
        for (let start = 0; start < width * height; start += 1) {
            if (pixels[start * 4 + 3] === 0 || labels[start]) continue;
            nextLabel += 1;
            const stack = [start];
            labels[start] = nextLabel;
            let size = 0;
            while (stack.length) {
                const point = stack.pop();
                size += 1;
                const x = point % width;
                const y = (point - x) / width;
                for (let dy = -1; dy <= 1; dy += 1) {
                    for (let dx = -1; dx <= 1; dx += 1) {
                        const nextX = x + dx;
                        const nextY = y + dy;
                        if (nextX < 0 || nextY < 0 || nextX >= width || nextY >= height) continue;
                        const next = nextY * width + nextX;
                        if (pixels[next * 4 + 3] !== 0 && !labels[next]) {
                            labels[next] = nextLabel;
                            stack.push(next);
                        }
                    }
                }
            }
            if (size > bestSize) {
                bestSize = size;
                bestLabel = nextLabel;
            }
        }
        for (let point = 0; point < width * height; point += 1) {
            if (pixels[point * 4 + 3] !== 0 && labels[point] !== bestLabel) pixels[point * 4 + 3] = 0;
        }

        const extra = Math.round(Number(settings.shoulders) * PIXEL);
        const outputWidth = width + extra * 2;
        const output = new ImageData(outputWidth, height);
        const outputPixels = output.data;
        for (let y = 0; y < height; y += 1) {
            let left = width;
            let right = -1;
            for (let x = 0; x < width; x += 1) {
                if (pixels[(y * width + x) * 4 + 3] > 0) {
                    left = Math.min(left, x);
                    right = Math.max(right, x);
                }
            }
            if (right < 0) continue;
            if (!(extra > 0 && y >= shirtTop && y < pantsTop)) {
                for (let x = left; x <= right; x += 1) {
                    const sourceIndex = (y * width + x) * 4;
                    const outputIndex = (y * outputWidth + x + extra) * 4;
                    outputPixels.set(pixels.subarray(sourceIndex, sourceIndex + 4), outputIndex);
                }
                continue;
            }
            const put = (sourceX, targetX) => {
                const sourceIndex = (y * width + sourceX) * 4;
                const outputIndex = (y * outputWidth + targetX + extra) * 4;
                outputPixels.set(pixels.subarray(sourceIndex, sourceIndex + 4), outputIndex);
            };
            for (let x = left; x < torsoLeft; x += 1) put(x, x - extra);
            for (let x = torsoLeft; x <= torsoRight; x += 1) put(x, x);
            for (let x = torsoRight + 1; x <= right; x += 1) put(x, x + extra);
            if (torsoLeft > left) for (let x = torsoLeft - extra; x < torsoLeft; x += 1) put(torsoLeft - 1, x);
            if (torsoRight < right) for (let x = torsoRight + 1; x < torsoRight + 1 + extra; x += 1) put(torsoRight + 1, x);
        }

        let headMin = outputWidth;
        let headMax = -1;
        for (let y = topY + 12; y < Math.min(height, topY + height * 0.12); y += 1) {
            for (let x = 0; x < outputWidth; x += 1) {
                if (outputPixels[(y * outputWidth + x) * 4 + 3] > 0) {
                    headMin = Math.min(headMin, x);
                    headMax = Math.max(headMax, x);
                }
            }
        }
        const headCenter = headMax >= 0 ? (headMin + headMax) / 2 : outputWidth / 2;
        const hasHat = settings.hat && hatImage?.complete && hatImage.naturalWidth;
        const hatExtra = hasHat ? Math.max(0, hatImage.height - HAT_OVERLAP - topY) : 0;
        const result = document.createElement('canvas');
        result.width = outputWidth;
        result.height = height + hatExtra;
        const resultContext = result.getContext('2d');
        resultContext.putImageData(output, 0, hatExtra);
        if (hasHat) {
            resultContext.drawImage(
                tintHat(hatImage, settings.hatColor),
                Math.round(headCenter - hatImage.width / 2),
                hatExtra + topY + HAT_OVERLAP - hatImage.height,
            );
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
            customSpriteCache.set(key, buildCustomSprite(
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
        const standing = buildCustomSprite(pictures.eve, pictures.hatStand, settings);
        const walking = buildCustomSprite(pictures.eveWalk, pictures.hatWalk, settings);
        const context = customPreview.getContext('2d');
        context.clearRect(0, 0, customPreview.width, customPreview.height);
        context.imageSmoothingEnabled = false;
        [standing, walking].forEach((sprite, index) => {
            if (!sprite?.width || !sprite?.height) return;
            const scale = Math.min(124 / sprite.height, 170 / sprite.width);
            const width = sprite.width * scale;
            const height = sprite.height * scale;
            context.drawImage(sprite, index * 180 + (180 - width) / 2, 148 - height, width, height);
            context.fillStyle = '#0b3d2e';
            context.textAlign = 'center';
            context.font = '12px Comfortaa, Arial, sans-serif';
            context.fillText(index ? 'Walking' : 'Standing', index * 180 + 90, 172);
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
        const targetX = Number(presence.x);
        const x = old ? old.x : targetX;
        remotePlayers.set(presence.id, {
            ...old,
            ...presence,
            x,
            targetX,
            walking: Boolean(old && Math.abs((old.targetX ?? old.x) - targetX) > 0.5),
            lastMovedAt: performance.now(),
        });
    };

    const applySnapshot = (data) => {
        if (data.player) setPlayer(data.player);
        if (Object.prototype.hasOwnProperty.call(data, 'crown_player_id')) {
            crownPlayerId = data.crown_player_id;
        }
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
                if (Object.prototype.hasOwnProperty.call(data, 'crown_player_id')) {
                    crownPlayerId = data.crown_player_id;
                }
            } else if (data.type === 'presence_left') {
                remotePlayers.delete(data.player_id);
                if (Object.prototype.hasOwnProperty.call(data, 'crown_player_id')) {
                    crownPlayerId = data.crown_player_id;
                }
            } else if (data.type === 'player_changed') {
                setPlayer(data.player);
                const remote = remotePlayers.get(data.player.id);
                if (remote) remote.donated_cans = data.player.donated_cans;
                if (Object.prototype.hasOwnProperty.call(data, 'crown_player_id')) {
                    crownPlayerId = data.crown_player_id;
                }
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
            if (event.code === 4409) {
                player = null;
                showAuth('This account was signed in elsewhere. Sign in again to take over.');
                setStatus('');
                return;
            }
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

    const prepareWorldAssets = () => {
        const background = pictures.background;
        if (roadMap || !background.complete || !background.naturalWidth) return;
        const width = background.naturalWidth;
        const height = background.naturalHeight;
        const source = document.createElement('canvas');
        source.width = width;
        source.height = height;
        const sourceContext = source.getContext('2d', { willReadFrequently: true });
        sourceContext.drawImage(background, 0, 0);
        const pixels = sourceContext.getImageData(0, 0, width, height).data;
        const nightPixels = pixels.slice();
        const tops = new Array(width).fill(436);
        const bottoms = new Array(width).fill(472);
        for (let x = 0; x < width; x += 1) {
            let top = -1;
            let bottom = -1;
            for (let y = 250; y < height; y += 1) {
                const index = (y * width + x) * 4;
                const red = pixels[index];
                const green = pixels[index + 1];
                const blue = pixels[index + 2];
                const sky = blue > 200 && red < 140;
                const grass = green > red + 30 && green > blue + 30;
                if (top < 0 && !sky && !grass) {
                    top = y;
                } else if (top >= 0 && grass) {
                    bottom = y;
                    break;
                }
            }
            if (top >= 0 && bottom > top) {
                tops[x] = top + ROAD_TOP_MARGIN;
                bottoms[x] = bottom - ROAD_BOTTOM_MARGIN;
            }
        }
        for (let y = 0; y < Math.min(height, 420); y += 1) {
            for (let x = 0; x < width; x += 1) {
                const index = (y * width + x) * 4;
                if (nightPixels[index + 2] - nightPixels[index] > 70 && nightPixels[index + 2] > 100) {
                    nightPixels[index] = 0;
                    nightPixels[index + 1] = 0;
                    nightPixels[index + 2] = 0;
                }
            }
        }
        const nightCanvas = document.createElement('canvas');
        nightCanvas.width = width;
        nightCanvas.height = height;
        nightCanvas.getContext('2d').putImageData(new ImageData(nightPixels, width, height), 0, 0);
        roadMap = { tops, bottoms };
        nightBackground = nightCanvas;
    };

    const backgroundColumn = (worldX) => {
        const width = pictures.background.naturalWidth;
        const tile = Math.floor(worldX / width);
        let column = Math.floor(worldX - tile * width);
        if (Math.abs(tile) % 2 === 1) column = width - 1 - column;
        return Math.max(0, Math.min(width - 1, column));
    };

    const roadFootY = (playerWorldX) => {
        if (!roadMap) return 456;
        let top = -Infinity;
        let bottom = Infinity;
        const worldX = canvas.width / 2 + playerWorldX;
        for (let offset = -14; offset <= 14; offset += 4) {
            const column = backgroundColumn(worldX + offset);
            top = Math.max(top, roadMap.tops[column]);
            bottom = Math.min(bottom, roadMap.bottoms[column]);
        }
        return (top + bottom) / 2;
    };

    const seededRandom = (seed) => {
        const value = Math.sin(seed * 127.1 + 311.7) * 43758.5453;
        return value - Math.floor(value);
    };
    const stars = Array.from({ length: 70 }, (_, index) => ({
        x: Math.floor(seededRandom(index + 1) * 940) + 8,
        y: Math.floor(seededRandom(index + 101) * 330) + 6,
        size: seededRandom(index + 201) < 0.25 ? 4 : 2,
        phase: seededRandom(index + 301) * 6.28,
    }));

    const drawClouds = (cameraX) => {
        const cloud = pictures.cloud;
        if (!cloud.complete || !cloud.naturalWidth) return;
        const cycle = canvas.width + cloud.naturalWidth;
        const drift = (performance.now() / 1000 * 18) % cycle;
        for (let index = 0; index < 5; index += 1) {
            const scale = 0.55 + seededRandom(index + 411) * 0.6;
            const width = cloud.naturalWidth * scale;
            const height = cloud.naturalHeight * scale;
            const base = index * (canvas.width / 5) + seededRandom(index + 421) * 120;
            const x = ((base - cameraX * 0.25 - drift) % cycle + cycle) % cycle - cloud.naturalWidth;
            const y = 10 + seededRandom(index + 431) * 100;
            ctx.drawImage(cloud, x, y, width, height);
        }
    };

    const drawHouses = (cameraX) => {
        const spacing = 2700;
        const first = Math.floor((cameraX - canvas.width) / spacing) - 1;
        const last = Math.ceil((cameraX + canvas.width) / spacing) + 1;
        const landmarks = [FEED_X, STORE_X, TRADING_X, BINGO_X, 0];
        for (let segment = first; segment <= last; segment += 1) {
            const worldX = segment * spacing + (seededRandom(segment + 511) - 0.5) * 800;
            if (landmarks.some((landmark) => Math.abs(worldX - landmark) < 520)) continue;
            const house = pictures.houses[Math.floor(seededRandom(segment + 521) * pictures.houses.length)];
            if (!house.complete || !house.naturalWidth) continue;
            const width = house.naturalWidth * HOUSE_SCALE;
            const height = house.naturalHeight * HOUSE_SCALE;
            const x = canvas.width / 2 + worldX - cameraX;
            if (x + width / 2 < 0 || x - width / 2 > canvas.width) continue;
            ctx.drawImage(house, x - width / 2, 412 - height, width, height);
        }
    };

    const drawTrees = (cameraX) => {
        const spacing = 820;
        const first = Math.floor((cameraX - canvas.width) / spacing) - 1;
        const last = Math.ceil((cameraX + canvas.width) / spacing) + 1;
        for (let segment = first; segment <= last; segment += 1) {
            const worldX = segment * spacing + (seededRandom(segment + 611) - 0.5) * 520;
            const tree = pictures.trees[Math.floor(seededRandom(segment + 621) * pictures.trees.length)];
            if (!tree.complete || !tree.naturalWidth) continue;
            const width = TREE_HEIGHT * tree.naturalWidth / tree.naturalHeight;
            const x = canvas.width / 2 + worldX - cameraX;
            if (x + width / 2 < 0 || x - width / 2 > canvas.width) continue;
            const base = 536 + seededRandom(segment + 631) * 12;
            ctx.drawImage(tree, x - width / 2, base - TREE_HEIGHT, width, TREE_HEIGHT);
        }
    };

    const drawBuilding = (image, worldX, scale, cameraX) => {
        if (!image.complete || !image.naturalWidth) return;
        const width = image.naturalWidth * scale;
        const height = image.naturalHeight * scale;
        const x = canvas.width / 2 + worldX - cameraX - width / 2;
        if (x > canvas.width || x + width < 0) return;
        ctx.drawImage(image, Math.round(x), Math.round(412 - height), Math.round(width), Math.round(height));
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
        const y = roadFootY(person.x);
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
        ctx.imageSmoothingEnabled = false;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        prepareWorldAssets();
        const background = isNight && nightBackground ? nightBackground : pictures.background;
        if (pictures.background.complete && pictures.background.naturalWidth) {
            const tileWidth = pictures.background.naturalWidth;
            const firstTile = Math.floor(cameraX / tileWidth);
            for (let tile = firstTile; tile * tileWidth - cameraX < canvas.width; tile += 1) {
                const x = Math.round(tile * tileWidth - cameraX);
                const mirrored = Math.abs(tile) % 2 === 1;
                ctx.save();
                if (mirrored) {
                    ctx.translate(x + tileWidth, 0);
                    ctx.scale(-1, 1);
                } else {
                    ctx.translate(x, 0);
                }
                ctx.drawImage(background, 0, 0);
                ctx.restore();
            }
        } else {
            ctx.fillStyle = '#56c8f2';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
        }
        drawClouds(cameraX);
        if (isNight) {
            const time = performance.now() / 1000;
            stars.forEach((star) => {
                ctx.globalAlpha = 0.65 + 0.35 * Math.sin(time * 2 + star.phase);
                ctx.fillStyle = '#fff';
                ctx.fillRect(star.x, star.y, star.size, star.size);
            });
            ctx.globalAlpha = 1;
            if (pictures.moon.complete && pictures.moon.naturalWidth && pictures.sun.complete && pictures.sun.naturalWidth) {
                const size = Math.max(pictures.sun.naturalWidth, pictures.sun.naturalHeight);
                const scale = size / Math.max(pictures.moon.naturalWidth, pictures.moon.naturalHeight);
                const width = Math.round(pictures.moon.naturalWidth * scale);
                const height = Math.round(pictures.moon.naturalHeight * scale);
                ctx.drawImage(
                    pictures.moon,
                    Math.round(800 + (pictures.sun.naturalWidth - width) / 2),
                    Math.round(34 + (pictures.sun.naturalHeight - height) / 2),
                    width,
                    height,
                );
            }
        } else if (pictures.sun.complete && pictures.sun.naturalWidth) {
            ctx.drawImage(pictures.sun, 800, 34);
        }

        drawHouses(cameraX);
        drawBuilding(pictures.sobeys, STORE_X, 0.85, cameraX);
        drawBuilding(pictures.feed, FEED_X, 0.75, cameraX);
        drawBuilding(pictures.trading, TRADING_X, 0.8, cameraX);
        drawBuilding(pictures.aj, BINGO_X, 0.7, cameraX);
        const active = [...remotePlayers.values()].filter((item) => item.id !== player?.id);
        const local = { ...player, x: localX };
        active.forEach((person) => drawPlayer(person, cameraX, false, crownPlayerId === person.id));
        drawPlayer(local, cameraX, true, crownPlayerId === player?.id);
        drawTrees(cameraX);
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
            if (direction) localX += direction * PLAYER_SPEED * dt;
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
        remotePlayers.forEach((remote) => {
            const distance = remote.targetX - remote.x;
            remote.x = Math.abs(distance) < 0.2
                ? remote.targetX
                : remote.x + distance * Math.min(1, dt * 12);
        });
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
