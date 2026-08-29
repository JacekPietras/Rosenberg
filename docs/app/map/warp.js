export const HRR_MAP_NATIVE_WIDTH = 3715;
export const HRR_MAP_NATIVE_HEIGHT = 3966;
export const HRR_MAP_CALIBRATION_SEED = { x0: 1637.1, y0: 1961.6, lon0: 11.3322, lat0: 49.4340, pxPerDegreeLon: 182.0, pxPerDegreeLat: -302.9 };

export function hrrCalibrationKeys(mapDef) {
  return { x: `calibrated_x_${mapDef.id}`, y: `calibrated_y_${mapDef.id}` };
}

export function hrrGuessPixelForLatLon(lat, lon, mapDef) {
  const scaleX = mapDef.width / HRR_MAP_NATIVE_WIDTH;
  const scaleY = mapDef.height / HRR_MAP_NATIVE_HEIGHT;
  const { x0, y0, lon0, lat0, pxPerDegreeLon, pxPerDegreeLat } = HRR_MAP_CALIBRATION_SEED;
  return { x: (x0 + (lon - lon0) * pxPerDegreeLon) * scaleX, y: (y0 + (lat - lat0) * pxPerDegreeLat) * scaleY };
}

export function hrrGuessLatLonForPixel(x, y, mapDef) {
  const scaleX = mapDef.width / HRR_MAP_NATIVE_WIDTH;
  const scaleY = mapDef.height / HRR_MAP_NATIVE_HEIGHT;
  const { x0, y0, lon0, lat0, pxPerDegreeLon, pxPerDegreeLat } = HRR_MAP_CALIBRATION_SEED;
  return { lat: lat0 + (y / scaleY - y0) / pxPerDegreeLat, lon: lon0 + (x / scaleX - x0) / pxPerDegreeLon };
}

function linearFit(xs, ys) {
  const n = xs.length;
  const meanX = xs.reduce((a, b) => a + b, 0) / n;
  const meanY = ys.reduce((a, b) => a + b, 0) / n;
  let numerator = 0;
  let denominator = 0;
  for (let i = 0; i < n; i++) {
    numerator += (xs[i] - meanX) * (ys[i] - meanY);
    denominator += (xs[i] - meanX) ** 2;
  }
  const slope = denominator === 0 ? 0 : numerator / denominator;
  return { slope, intercept: meanY - slope * meanX };
}

function solveLinearSystem(matrix, rhs) {
  const n = rhs.length;
  const rows = matrix.map((row, i) => [...row, rhs[i]]);
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let row = col + 1; row < n; row++) if (Math.abs(rows[row][col]) > Math.abs(rows[pivot][col])) pivot = row;
    [rows[col], rows[pivot]] = [rows[pivot], rows[col]];
    const pivotValue = rows[col][col];
    for (let row = 0; row < n; row++) {
      if (row === col) continue;
      const factor = rows[row][col] / pivotValue;
      for (let cell = col; cell <= n; cell++) rows[row][cell] -= factor * rows[col][cell];
    }
  }
  return rows.map((row, index) => row[n] / row[index]);
}

function fitThinPlateSpline(points, values) {
  const n = points.length;
  const size = n + 3;
  const matrix = Array.from({ length: size }, () => new Array(size).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const radius = Math.hypot(points[i].x - points[j].x, points[i].y - points[j].y);
      matrix[i][j] = radius <= 1e-9 ? 0 : radius * radius * Math.log(radius);
    }
    matrix[i][n] = 1;
    matrix[i][n + 1] = points[i].x;
    matrix[i][n + 2] = points[i].y;
    matrix[n][i] = 1;
    matrix[n + 1][i] = points[i].x;
    matrix[n + 2][i] = points[i].y;
  }
  const solution = solveLinearSystem(matrix, [...values, 0, 0, 0]);
  const weights = solution.slice(0, n);
  const [a0, a1, a2] = solution.slice(n);
  return (x, y) => {
    let sum = a0 + a1 * x + a2 * y;
    for (let i = 0; i < n; i++) {
      const radius = Math.hypot(x - points[i].x, y - points[i].y);
      if (radius > 1e-9) sum += weights[i] * radius * radius * Math.log(radius);
    }
    return sum;
  };
}

export function hrrBuildWarp(places, mapDef) {
  const { x: keyX, y: keyY } = hrrCalibrationKeys(mapDef);
  const controls = places
    .filter((place) => Number.isFinite(place[keyX]) && Number.isFinite(place[keyY]))
    .map((place) => ({ lat: place.lat, lon: place.lon, x: place[keyX], y: place[keyY] }));
  if (controls.length >= 3) {
    const realCoordinates = controls.map((control) => ({ x: control.lon, y: control.lat }));
    const pixelX = fitThinPlateSpline(realCoordinates, controls.map((control) => control.x));
    const pixelY = fitThinPlateSpline(realCoordinates, controls.map((control) => control.y));
    return { pixelForLatLon: (lat, lon) => ({ x: pixelX(lon, lat), y: pixelY(lon, lat) }) };
  }
  if (controls.length === 2) {
    const fitX = linearFit(controls.map((control) => control.lon), controls.map((control) => control.x));
    const fitY = linearFit(controls.map((control) => control.lat), controls.map((control) => control.y));
    return { pixelForLatLon: (lat, lon) => ({ x: fitX.intercept + fitX.slope * lon, y: fitY.intercept + fitY.slope * lat }) };
  }
  return { pixelForLatLon: (lat, lon) => hrrGuessPixelForLatLon(lat, lon, mapDef) };
}

function solve2x2(a, b, c, d, e, f) {
  const determinant = a * d - b * c;
  if (Math.abs(determinant) < 1e-9) return null;
  return { x: (e * d - b * f) / determinant, y: (a * f - e * c) / determinant };
}

function invertPixelForLatLon(pixelForLatLon, targetX, targetY, mapDef) {
  const seed = hrrGuessLatLonForPixel(targetX, targetY, mapDef);
  let lat = seed.lat;
  let lon = seed.lon;
  const epsilon = 0.02;
  for (let iteration = 0; iteration < 25; iteration++) {
    const point = pixelForLatLon(lat, lon);
    const residualX = point.x - targetX;
    const residualY = point.y - targetY;
    if (Math.abs(residualX) < 0.05 && Math.abs(residualY) < 0.05) break;
    const pointLat = pixelForLatLon(lat + epsilon, lon);
    const pointLon = pixelForLatLon(lat, lon + epsilon);
    const delta = solve2x2(
      (pointLat.x - point.x) / epsilon,
      (pointLon.x - point.x) / epsilon,
      (pointLat.y - point.y) / epsilon,
      (pointLon.y - point.y) / epsilon,
      -residualX,
      -residualY,
    );
    if (!delta) break;
    lat += delta.x;
    lon += delta.y;
  }
  return { lat, lon };
}

export function hrrBuildInverseWarp(places, mapDef) {
  const warp = hrrBuildWarp(places, mapDef);
  return { latLonForPixel: (x, y) => invertPixelForLatLon(warp.pixelForLatLon, x, y, mapDef) };
}
