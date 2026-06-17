/**
 * Расчёт эталонных пипсов из снимка доски (sharedContext / payload.board).
 */

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
    if (!snapshot || typeof snapshot !== 'object') return null;
    const pos = snapshot.positions;
    if (!pos || typeof pos !== 'object') return null;

    const red = pos.red;
    const black = pos.black;
    if (!red || !black) return null;

    const invert = !!snapshot.invertColors;

    const whitePips = invert
        ? calculatePipsForPositions(red, 'second')
        : calculatePipsForPositions(red, 'first');
    const blackPips = invert
        ? calculatePipsForPositions(black, 'first')
        : calculatePipsForPositions(black, 'second');

    if (!invert) {
        return { upperPips: blackPips, lowerPips: whitePips };
    }
    return { upperPips: whitePips, lowerPips: blackPips };
}

/**
 * @param {object | null | undefined} payload — кадр с board / sharedContext
 * @param {object | null | undefined} [sharedContext]
 */
export function resolveReferencePipsFromPayload(payload, sharedContext) {
    const board =
        (payload && payload.board) ||
        (sharedContext && sharedContext.board) ||
        null;
    return resolveReferencePips(board);
}
