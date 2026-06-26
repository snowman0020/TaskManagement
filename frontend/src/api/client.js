import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
})

// Attach JWT to every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Bounce to login on auth failure (expired token, or a disabled account)
client.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status
    const disabled =
      status === 403 && err.response?.data?.detail === 'User is disabled'
    if (status === 401 || disabled) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (location.pathname !== '/login') location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default client
