import axios from 'axios';

const axiosInstance = axios.create({
  baseURL: '/api2',
  timeout: 300000, // 300 seconds
  withCredentials: true,
});

function nativeErrorMessage(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.flatMap(item =>
      item && typeof item === 'object' && typeof item.msg === 'string' ? [item.msg] : [],
    ).join('; ');
  }
  if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') {
    return detail.message;
  }
}

// Keep error presentation stable while the UI moves to the native API contracts.
axiosInstance.interceptors.response.use(response => response, (error: unknown) => {
  if (axios.isAxiosError<Record<string, unknown>>(error)) {
    const payload = error.response?.data;
    if (payload && typeof payload === 'object' && !payload.error) {
      const message = nativeErrorMessage(payload.detail);
      if (message) payload.error = message;
    }
  }
  return Promise.reject(error);
});

export default axiosInstance;
