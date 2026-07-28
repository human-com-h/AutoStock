import axios from "axios";

export const http = axios.create({ baseURL: "/api", withCredentials: true, timeout: 10000 });

http.interceptors.response.use(
  (response) => response.data?.data ?? response.data,
  (error) => {
    const data = error.response?.data;
    let message = data?.error?.message;
    if (!message && Array.isArray(data?.detail)) {
      message = "请求参数不正确，请检查后重试";
    }
    return Promise.reject(new Error(message || error.message || "请求失败，请稍后重试"));
  },
);
