// Cloudflare Pages Function: every /api/* request goes to the shared handler. Secrets arrive in `env`.
import { handle } from "../../lib/api.js";

export const onRequest = ({ request, env }) => handle(request, env);
