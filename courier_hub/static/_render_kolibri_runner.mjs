import { pathToFileURL } from "node:url";
const mod = await import(pathToFileURL(process.argv[2]).href);
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const snapshot = JSON.parse(Buffer.concat(chunks).toString("utf8"));
const html = mod.renderKolibri(snapshot);
process.stdout.write(JSON.stringify({ html, poll: mod.POLL_MS, rest: mod.REST_TEXT }));
