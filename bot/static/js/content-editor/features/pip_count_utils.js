/**
 * Расчёт эталонных пипсов из снимка доски (sharedContext / payload.board).
 */

function getDefaultStartPositions(invertColors) {
    if (invertColors) {
        return {
            red: { '1': 2, '12': 5, '17': 3, '19': 5, bar: 0, off: 0 },
            black: { '6': 5, '8': 3, '13': 5, '24': 2, bar: 0, off: 0 },
        };
    }
    return {
        red: { '24': 2, '6': 5, '8': 3, '13': 5, bar: 0, off: 0 },
        black: { '1': 2, '19': 5, '17': 3, '12': 5, bar: 0, off: 0 },
    };
}

/**
 * Те же red/black, что у paintBoardPreviewCanvas / resolveBoardPositionsFromSnapshot.
 * @param {object | null | undefined} snapshot
 * @returns {{ red: object, black: object, invert: boolean } | null}
 */
function resolveRedBlackFromSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== 'object') return null;
    if (snapshot.error === 'no_game_data') return null;

    const invert = !!snapshot.invertColors;
    const pos = snapshot.positions;
    if (pos && typeof pos === 'object' && pos.red && pos.black) {
        return { red: pos.red, black: pos.black, invert };
    }

    const fi = snapshot.frameIndex;
    if (fi === 0 || fi === null || fi === undefined) {
        const defs = getDefaultStartPositions(invert);
        return { red: defs.red, black: defs.black, invert };
    }

    return null;
}

function calculatePipsForPositions(positions, playerRole) {
    if (!positions || typeof positions !== 'object') return 0;
    let totalPips = 0;
    for (const pointStr in positions) {
        if (!Object.prototype.hasOwnProperty.call(positions, pointStr)) continue;
        if (pointStr === 'bar') {
            totalPips += Math.abs(Number(positions[pointStr]) || 0) * 25;
        } else if (pointStr === 'off') {
            continue;
        } else {
            const point = parseInt(pointStr, 10);
            const count = Number(positions[pointStr]) || 0;
            if (!Number.isFinite(point) || !count) continue;
            const effectivePoint = playerRole === 'second' ? 25 - point : point;
            totalPips += count * effectivePoint;
        }
    }
    return totalPips;
}

/**
 * @param {object | null | undefined} snapshot — board из карточки / hint viewer
 * @returns {{ upperPips: number, lowerPips: number } | null}
 */
export function resolveReferencePips(snapshot) {
    const rb = resolveRedBlackFromSnapshot(snapshot);
    if (!rb) return null;

    const whitePips = rb.invert
        ? calculatePipsForPositions(rb.red, 'second')
        : calculatePipsForPositions(rb.red, 'first');
    const blackPips = rb.invert
        ? calculatePipsForPositions(rb.black, 'first')
        : calculatePipsForPositions(rb.black, 'second');

    if (!rb.invert) {
        return { upperPips: blackPips, lowerPips: whitePips };
    }
    return { upperPips: whitePips, lowerPips: blackPips };
}

function tryResolveFromBoard(board) {
    if (!board || typeof board !== 'object') return null;
    return resolveReferencePips(board);
}

/**
 * @param {object | null | undefined} payload — кадр с board / sharedContext
 * @param {object | null | undefined} [sharedContext]
 */
export function resolveReferencePipsFromPayload(payload, sharedContext) {
    const fromPayload = tryResolveFromBoard(payload && payload.board);
    if (fromPayload) return fromPayload;

    const fromShared = tryResolveFromBoard(sharedContext && sharedContext.board);
    if (fromShared) return fromShared;

    if (typeof window !== 'undefined' && typeof window.getHintViewerBoardSnapshot === 'function') {
        try {
            const live = window.getHintViewerBoardSnapshot();
            if (live && typeof live === 'object' && live.error !== 'no_game_data') {
                const fromLive = resolveReferencePips(live);
                if (fromLive) return fromLive;
            }
        } catch (_e) {
            /* noop */
        }
    }

    return null;
}
