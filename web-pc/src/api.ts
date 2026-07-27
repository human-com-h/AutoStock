import axios from "axios";

export const http = axios.create({ baseURL: "/api", withCredentials: true, timeout: 10000 });

http.interceptors.response.use(
  (response) => response.data?.data ?? response.data,
  (error) => Promise.reject(new Error(error.response?.data?.error?.message || error.message)),
);
