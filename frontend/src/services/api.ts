import axios from "axios"

const apiUrl = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")

const API = axios.create({
  baseURL: apiUrl,
  timeout: 20000
})

export default API
