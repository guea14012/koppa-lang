/**
 * APOLLO Deno Runtime v1.0
 * Provides built-in functions and pipeline support for transpiled APOLLO scripts
 */

// --- Core Runtime Functions ---

/**
 * Pipeline operator implementation (a |> b)
 * In JS: pipe(a, b)
 */
export function pipe(val: any, fn: Function): any {
  return fn(val);
}

/**
 * Built-in log module
 */
export const log = {
  info: (msg: string) => console.log(`[%cINFO%c] ${msg}`, "color: blue", ""),
  warn: (msg: string) => console.log(`[%cWARN%c] ${msg}`, "color: yellow", ""),
  error: (msg: string) => console.error(`[%cERROR%c] ${msg}`, "color: red", ""),
  success: (msg: string) => console.log(`[%cSUCCESS%c] ${msg}`, "color: green", ""),
};

/**
 * Built-in scan module (mock/simulated for now, can use Deno.connect)
 */
export const scan = {
  tcp: async (host: string, port: number): Promise<boolean> => {
    try {
      const conn = await Deno.connect({ hostname: host, port: port, transport: "tcp" });
      conn.close();
      return true;
    } catch {
      return false;
    }
  },
  
  service: (port: number): string => {
    const services: Record<number, string> = {
      21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
      53: "dns", 80: "http", 443: "https", 445: "microsoft-ds",
      3306: "mysql", 3389: "ms-wbt-server", 5432: "postgresql",
      8080: "http-proxy"
    };
    return services[port] || "unknown";
  }
};

/**
 * Built-in report module
 */
export const report = {
  save: (data: any, filename: string) => {
    const content = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    Deno.writeTextFileSync(filename, content);
    log.success(`Report saved to ${filename}`);
    return data;
  },
  finding: (type: string, severity: string, description: string) => ({
    type, severity, description, timestamp: new Date().toISOString()
  })
};

/**
 * Built-in http module
 */
export const http = {
  get: async (url: string) => {
    const resp = await fetch(url);
    return {
      status: resp.status,
      headers: Object.fromEntries(resp.headers.entries()),
      body: await resp.text()
    };
  },
  post: async (url: string, data: any) => {
    const resp = await fetch(url, {
      method: 'POST',
      body: JSON.stringify(data),
      headers: { 'Content-Type': 'application/json' }
    });
    return {
      status: resp.status,
      body: await resp.text()
    };
  }
};

/**
 * Standard utility: sleep
 */
export const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Default value operator (val | default("foo"))
 */
export function defaultValue(val: any, def: any): any {
  return (val === undefined || val === null) ? def : val;
}

// Global scope initialization if needed
// @ts-ignore
globalThis.pipe = pipe;
// @ts-ignore
globalThis.log = log;
// @ts-ignore
globalThis.scan = scan;
// @ts-ignore
globalThis.report = report;
// @ts-ignore
globalThis.http = http;
// @ts-ignore
globalThis.sleep = sleep;
