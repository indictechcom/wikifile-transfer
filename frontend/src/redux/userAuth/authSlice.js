import { createSlice, createAsyncThunk } from "@reduxjs/toolkit";
import backendApi from "../../utils/api";

export const userSlice = createSlice({
  name: "userAuth",
  initialState: {
    loading: false,
    error: null,
    logged: false,
    username: null,
  },
  reducers: {
    setUserLoading: (state) => {
      state.loading = true;
    },
    setUserSuccess: (state, action) => {
      state.loading = false;
      state.logged = action.payload.logged;
      state.username = action.payload.username;
    },
    setUserError: (state, action) => {
      state.loading = false;
      state.error = action.payload;
    },
    resetUser: (state) => {
      state.loading = false;
      state.error = null;
      state.logged = false;
      state.username = null;
    },
  },
});

export const { setUserLoading, setUserSuccess, setUserError, resetUser } =
  userSlice.actions;

export const fetchUser = createAsyncThunk(
  "userAuth/fetchUser",
  async (_, { dispatch, rejectWithValue }) => {
    try {
      dispatch(setUserLoading());
      const response = await backendApi.get("/api/user");
      dispatch(setUserSuccess(response.data));
    } catch (error) {
      dispatch(setUserError(error.response.data));
      return rejectWithValue(error.response.data);
    }
  }
);

export default userSlice.reducer;
