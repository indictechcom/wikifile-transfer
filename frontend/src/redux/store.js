import { configureStore } from '@reduxjs/toolkit'
import userAuth from './userAuth/authSlice'

export const store = configureStore({
  reducer: {
    auth: userAuth,
  },
})