import axios from "axios";

const LOCALHOST_FALLBACK_URL = "http://localhost:8000";

export function normalizeApiBaseUrl(value) {
  const trimmedValue = value?.trim();

  if (!trimmedValue) {
    return LOCALHOST_FALLBACK_URL;
  }

  const valueWithProtocol = /^https?:\/\//i.test(trimmedValue)
    ? trimmedValue
    : `http://${trimmedValue}`;

  return valueWithProtocol.replace(/\/+$/, "");
}

export function getDefaultApiBaseUrl() {
  return normalizeApiBaseUrl(
    process.env.EXPO_PUBLIC_API_URL ||
      process.env.REACT_APP_API_URL ||
      LOCALHOST_FALLBACK_URL,
  );
}

function getErrorMessage(error) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    "Something went wrong."
  );
}

export function createMobileApi({ baseURL, getToken, onUnauthorized }) {
  const client = axios.create({
    baseURL: normalizeApiBaseUrl(baseURL),
    headers: {
      "Content-Type": "application/json",
    },
    timeout: 15000,
  });

  client.interceptors.request.use(async (config) => {
    const token = await Promise.resolve(getToken?.());

    if (token) {
      config.headers.Authorization = "Bearer " + token;
    }

    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      if (error?.response?.status === 401 && onUnauthorized) {
        await onUnauthorized();
      }

      return Promise.reject(error);
    },
  );

  const request = async (config) => {
    try {
      const response = await client.request(config);
      return response.data;
    } catch (error) {
      const normalizedError = new Error(getErrorMessage(error));
      normalizedError.status = error?.response?.status;
      normalizedError.payload = error?.response?.data;
      throw normalizedError;
    }
  };

  return {
    health: () =>
      request({
        method: "GET",
        url: "/api/health",
      }),
    login: (email, password) =>
      request({
        method: "POST",
        url: "/api/auth/login",
        data: { email, password },
      }),
    getDashboard: () =>
      request({
        method: "GET",
        url: "/api/dashboard/",
      }),
    getInventory: () =>
      request({
        method: "GET",
        url: "/api/inventory/",
      }),
    getMaterialOptions: () =>
      request({
        method: "GET",
        url: "/api/inventory/materials",
      }),
    addInventoryItem: (data) =>
      request({
        method: "POST",
        url: "/api/inventory/",
        data,
      }),
    getClients: () =>
      request({
        method: "GET",
        url: "/api/clients/",
      }),
    addClient: (data) =>
      request({
        method: "POST",
        url: "/api/clients/",
        data,
      }),
    getPayments: () =>
      request({
        method: "GET",
        url: "/api/payments/",
      }),
    addPayment: (data) =>
      request({
        method: "POST",
        url: "/api/payments/",
        data,
      }),
    sendChatMessage: (message, conversationId) =>
      request({
        method: "POST",
        url: "/api/chat/",
        data: {
          message,
          conversation_id: conversationId || null,
        },
      }),
  };
}
