import http from 'k6/http';
import { check, sleep } from 'k6';

// Mixed workload for the envelope-encryption API.
// 70% create, 30% read. Read uses one record created in setup() so the
// workload does not measure 404s. All values are synthetic demo data.
//
// SLEEP (seconds, default 0) paces iterations; use SLEEP>0 for the T16
// false-positive test so the normal load stays below the alert threshold.
//
// Run through Docker so the host does not need k6 installed:
//   docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
//     -e BASE_URL=http://host.docker.internal:8000 `
//     -e API_KEY=local-demo-api-key-change-me `
//     -e VUS=50 -e DURATION=3m `
//     --out csv=bench/results/D-lab_50_run1.csv bench/k6/mixed.js

const BASE_URL = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const API_KEY = __ENV.API_KEY || '';
const SLEEP = Number(__ENV.SLEEP || 0);

if (!API_KEY) {
  throw new Error('Set API_KEY to the demo API key (see student2_project_windows/.env.example)');
}

export const options = {
  scenarios: {
    mixed: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || 50),
      duration: __ENV.DURATION || '3m',
      gracefulStop: '30s',
    },
  },
  thresholds: {
    // H2: accept less than 0.1% failed requests during steady state/rotation.
    http_req_failed: ['rate<0.001'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export function setup() {
  const res = http.post(
    `${BASE_URL}/records`,
    JSON.stringify({ record_type: 'bench_phone', value: '0901234567' }),
    {
      headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
      tags: { operation: 'setup' },
    },
  );

  check(res, { 'setup create 201': (r) => r.status === 201 });
  if (res.status !== 201) {
    throw new Error(`Setup failed: HTTP ${res.status} ${res.body}`);
  }

  return { recordId: res.json('id') };
}

export default function (data) {
  if (Math.random() < 0.7) {
    const suffix = ((__VU * 100000 + __ITER) % 10000000).toString().padStart(7, '0');
    const res = http.post(
      `${BASE_URL}/records`,
      JSON.stringify({ record_type: 'bench_phone', value: `090${suffix}` }),
      {
        headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
        tags: { operation: 'create' },
      },
    );
    check(res, { 'create 201': (r) => r.status === 201 });
  } else {
    const res = http.get(`${BASE_URL}/records/${data.recordId}`, {
      headers: { 'X-API-Key': API_KEY },
      tags: { operation: 'read' },
    });
    check(res, { 'read 200': (r) => r.status === 200 });
  }
  if (SLEEP > 0) {
    sleep(SLEEP);
  }
}
