import axios from 'axios';


const baseUrl = process.env.NODE_ENV === 'development' ? 'http://localhost:5001/' : 'https://wikifile-transfer.toolforge.org/';

export const backendApi = axios.create({
  baseURL: baseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

export default backendApi;