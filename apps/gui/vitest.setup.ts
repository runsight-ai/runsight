const NativeRequest = globalThis.Request;
if (NativeRequest) {
  class RequestWithCompatibleSignal extends NativeRequest {
    constructor(input: RequestInfo | URL, init?: RequestInit) {
      if (init?.signal) {
        const { signal: _signal, ...rest } = init;
        init = rest;
      }

      super(input, init);
    }
  }

  Object.defineProperty(globalThis, "Request", {
    value: RequestWithCompatibleSignal,
    writable: true,
    configurable: true,
  });
}
