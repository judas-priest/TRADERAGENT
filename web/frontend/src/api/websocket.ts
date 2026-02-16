type MessageHandler = (data: WebSocketMessage) => void;

export interface WebSocketMessage {
  type: string;
  channel?: string;
  data?: Record<string, unknown>;
  timestamp?: number;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private handlers: Set<MessageHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private url: string;

  constructor(baseUrl: string) {
    this.url = baseUrl.replace(/^http/, 'ws');
  }

  connect(token: string, botName?: string) {
    const path = botName ? `/ws/bots/${botName}` : '/ws/events';
    const wsUrl = `${this.url}${path}?token=${token}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        if (message.type === 'ping') {
          this.ws?.send('pong');
          return;
        }
        this.handlers.forEach((handler) => handler(message));
      } catch {
        // ignore parse errors
      }
    };

    this.ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(token, botName), 5000);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  onMessage(handler: MessageHandler) {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  get isConnected() {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
