import axios from 'axios';

const baseUrl = window.location.hostname === 'localhost' ? 'http://localhost:5000/' : 'https://wikifile-transfer.toolforge.org/';

export const backendApi = axios.create({
  baseURL: baseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

export default backendApi;
