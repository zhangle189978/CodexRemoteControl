import { DWClient, TOPIC_ROBOT } from "dingtalk-stream";

const clientId = requiredEnv("DINGTALK_CLIENT_ID");
const clientSecret = requiredEnv("DINGTALK_CLIENT_SECRET");
const localWebhookUrl = process.env.CODEX_REMOTE_DINGTALK_WEBHOOK_URL
  || "http://127.0.0.1:8765/dingtalk/webhook";
const gatewayToken = process.env.DINGTALK_GATEWAY_TOKEN || "";
const endpoint = process.env.DINGTALK_ENDPOINT || "https://api.dingtalk.com";
const debug = process.env.DINGTALK_DEBUG === "true";

const client = new DWClient({
  clientId,
  clientSecret,
  endpoint,
  debug,
  autoReconnect: true,
  keepAlive: true,
});

client.registerCallbackListener(TOPIC_ROBOT, async (message) => {
  const messageId = message.headers?.messageId;
  if (messageId) {
    client.socketCallBackResponse(messageId, { success: true });
  }

  let data;
  try {
    data = JSON.parse(message.data);
  } catch (error) {
    console.error("[dingtalk-stream] invalid JSON payload:", error);
    return;
  }

  const payload = normalizePayload(data, gatewayToken);
  console.log(
    `[dingtalk-stream] inbound ${payload.msgId || messageId || "unknown"} `
      + `from ${payload.senderStaffId || payload.senderId || "unknown"}`,
  );

  try {
    const response = await fetch(localWebhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const responseBody = await response.json().catch(() => ({}));
    const text = responseBody?.text?.content || responseBody?.text || "";
    if (text) {
      await sendTextReply(data, text);
    }
  } catch (error) {
    console.error("[dingtalk-stream] local webhook failed:", error);
  }
});

client.on("connect", () => console.log("[dingtalk-stream] connected"));
client.on("disconnect", () => console.warn("[dingtalk-stream] disconnected"));
client.on("error", (error) => console.error("[dingtalk-stream] error:", error));

await client.connect();
console.log("[dingtalk-stream] bridge started");

function normalizePayload(data, token) {
  return {
    token,
    msgId: data.msgId || data.messageId || "",
    messageId: data.msgId || data.messageId || "",
    conversationId: data.conversationId || "",
    conversationType: data.conversationType || "",
    senderStaffId: data.senderStaffId || "",
    senderId: data.senderId || "",
    senderNick: data.senderNick || "",
    robotCode: data.robotCode || clientId,
    text: data.text || data.content || "",
  };
}

async function sendTextReply(inbound, content) {
  const accessToken = await getAccessToken();
  const isGroup = String(inbound.conversationType) === "2";
  const url = isGroup
    ? "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
    : "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend";
  const body = isGroup
    ? {
        robotCode: inbound.robotCode || clientId,
        openConversationId: inbound.conversationId,
        msgKey: "sampleText",
        msgParam: JSON.stringify({ content }),
      }
    : {
        robotCode: inbound.robotCode || clientId,
        userIds: [inbound.senderStaffId || inbound.senderId].filter(Boolean),
        msgKey: "sampleText",
        msgParam: JSON.stringify({ content }),
      };

  if (!isGroup && body.userIds.length === 0) {
    console.warn("[dingtalk-stream] cannot reply: missing sender user id");
    return;
  }
  if (isGroup && !body.openConversationId) {
    console.warn("[dingtalk-stream] cannot reply: missing conversation id");
    return;
  }

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-acs-dingtalk-access-token": accessToken,
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`DingTalk send failed ${response.status}: ${errorText}`);
  }
}

let cachedToken = "";
let cachedTokenExpiresAt = 0;

async function getAccessToken() {
  const now = Date.now();
  if (cachedToken && cachedTokenExpiresAt > now + 60_000) {
    return cachedToken;
  }
  const response = await fetch("https://api.dingtalk.com/v1.0/oauth2/accessToken", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ appKey: clientId, appSecret: clientSecret }),
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`DingTalk access token failed ${response.status}: ${errorText}`);
  }
  const body = await response.json();
  cachedToken = body.accessToken;
  cachedTokenExpiresAt = now + Number(body.expireIn || 0) * 1000;
  return cachedToken;
}

function requiredEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}
