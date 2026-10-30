import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Counter, Rate, Trend } from 'k6/metrics';
import exec from 'k6/execution';

const target = __ENV.BASE_URL || 'http://127.0.0.1:8000';
if (__ENV.ALLOW_ISOLATED_LOAD !== 'YES_NONPRODUCTION' || !__ENV.ALLOWED_LOAD_HOST
    || !/^https?:\/\/[^/?#]+/.test(target)
    || target.replace(/^https?:\/\//,'').split(/[/:?#]/)[0] !== __ENV.ALLOWED_LOAD_HOST) {
  throw new Error('Explicit isolated-host acknowledgement required. Production load is prohibited.');
}
const accounts = new SharedArray('accounts', () => JSON.parse(open(__ENV.ACCOUNTS_FILE || '/tmp/schoolwall-load/accounts.json')).accounts);
const ids = new SharedArray('post_ids', () => JSON.parse(open(__ENV.ACCOUNTS_FILE || '/tmp/schoolwall-load/accounts.json')).post_ids);
const profile = __ENV.PROFILE || 'steady';
if (!['steady', 'burst', 'soak'].includes(profile)) throw new Error('Unknown PROFILE');
const rate = Number(__ENV.RATE || (profile === 'burst' ? 200 : 100));
const duration = __ENV.DURATION || ({steady:'30m', burst:'5m', soak:'8h'}[profile]);
const rejected = new Counter('expected_rate_rejections');
const serverErrors = new Rate('server_errors');
const readDuration = new Trend('read_duration', true);
const writeDuration = new Trend('write_duration', true);
export const options = {
  scenarios: { campus: { executor:'constant-arrival-rate', rate, duration, timeUnit:'1s',
    preAllocatedVUs:Number(__ENV.VUS || 100), maxVUs:Number(__ENV.MAX_VUS || 500) } },
  thresholds: {
    read_duration:['p(95)<=500'],
    write_duration:['p(95)<=800'],
    server_errors:['rate<0.001'],
    http_req_failed:['rate<0.01'],
    checks:['rate>0.99'],
    dropped_iterations:['count==0'],
  },
  summaryTrendStats:['avg','p(50)','p(95)','p(99)','max'],
};
// 429 is counted separately and fails the business-success check below.
http.setResponseCallback(http.expectedStatuses({min:200,max:299},429));

function send(method,path,body,token,name) {
  const r = http.request(method,target+path,body ? JSON.stringify(body) : null,{
    headers:{'Content-Type':'application/json','Authorization': 'Bearer '+token},
    tags:{name},timeout:'10s',
  });
  if (r.status === 429) rejected.add(1);
  serverErrors.add(r.status >= 500 && r.status < 600);
  (method === 'GET' ? readDuration : writeDuration).add(r.timings.duration);
  check(r, {'successful business response': x => x.status>=200 && x.status<300});
  return r;
}
export default function () {
  const sequence = exec.scenario.iterationInTest;
  const token = accounts[sequence % accounts.length].token;
  const hot = Math.random() < 0.8;
  const id = hot ? ids[0] : ids[Math.floor(Math.random()*ids.length)];
  const kind = sequence % 100;
  if(kind < 45) send('GET','/api/v1/posts?limit=20&order=time',null,token,'feed');
  else if(kind < 70) send('GET','/api/v1/posts/'+id,null,token,'post_detail');
  else if(kind < 80) send('GET','/api/v1/posts/hot',null,token,'hot');
  else if(kind < 87) send('GET','/api/v1/posts/search?q=course',null,token,'search');
  else if(kind < 93) {
    if ((Math.floor(sequence / accounts.length) + sequence % 2) % 2 === 0) send('POST','/api/v1/posts/'+id+'/like',{},token,'like');
    else send('DELETE','/api/v1/posts/'+id+'/like',null,token,'unlike');
  } else if(kind < 97) send('POST','/api/v1/posts/'+id+'/comments',{content:'Synthetic nonproduction campus load '+sequence},token,'comment');
  else send('GET','/api/v1/notifications/unread-summary',null,token,'unread');
  sleep(Math.random()*0.2);
}
