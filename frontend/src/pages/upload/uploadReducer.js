export const initialUploadState = {
  activeStep: 0,
  loading: false,
  error: null,
  validationError: null,
  showResult: false,
  skipUploadSelection: false,
  sourceUrl: "",
  project: "",
  languages: [],
  languageData: {},
  activeTabs: { 2: 0, 3: 0, 4: 0 },
  successTab: 0,
  pendingTasks: {},
  uploadResults: {},
  editableWikitexts: {},
  editingState: {},
  articleEditSuccess: {},
};

export function uploadReducer(state, action) {
  switch (action.type) {
    case "SET_ACTIVE_STEP":
      return { ...state, activeStep: action.payload };
    case "NEXT_STEP":
      return { ...state, activeStep: state.activeStep + 1, validationError: null };
    case "PREV_STEP":
      return { ...state, activeStep: state.activeStep - 1, validationError: null };
    case "SKIP_TO_STEP":
      return { ...state, activeStep: action.payload, validationError: null };
    case "SET_SOURCE_URL":
      return { ...state, sourceUrl: action.payload };
    case "SET_PROJECT":
      return { ...state, project: action.payload, languages: [] };
    case "SET_LANGUAGES":
      return { ...state, languages: action.payload };
    case "UPDATE_LANGUAGE_DATA": {
      const { lang, field, value } = action.payload;
      return {
        ...state,
        languageData: {
          ...state.languageData,
          [lang]: {
            ...state.languageData[lang],
            [field]: value,
          },
        },
      };
    }
    case "BATCH_INIT_LANGUAGE_DATA": {
      const { languages, defaultFileName } = action.payload;
      const newData = { ...state.languageData };
      let changed = false;

      languages.forEach((lang) => {
        if (!newData[lang]) {
          newData[lang] = {};
        }

        if (defaultFileName && !newData[lang].targetFileName) {
          newData[lang].targetFileName = defaultFileName;
          changed = true;
        }

        if (newData[lang].pageContent === undefined) {
          newData[lang].pageContent = "";
          changed = true;
        }
      });

      return changed ? { ...state, languageData: newData } : state;
    }
    case "SET_ACTIVE_TAB": {
      const { step, index } = action.payload;
      return {
        ...state,
        activeTabs: {
          ...state.activeTabs,
          [step]: index,
        },
      };
    }
    case "SET_SUCCESS_TAB":
      return { ...state, successTab: action.payload };
    case "SET_LOADING":
      return { ...state, loading: action.payload };
    case "SET_ERROR":
      return { ...state, error: action.payload };
    case "UPLOAD_FAILURE":
      return {
        ...state,
        loading: false,
        showResult: false,
        pendingTasks: {},
        error: action.payload,
      };
    case "SET_VALIDATION_ERROR":
      return { ...state, validationError: action.payload };
    case "UPLOAD_SYNC_SUCCESS":
    case "UPLOAD_COMPLETED": {
      const { results, editableWikitexts } = action.payload;
      return {
        ...state,
        uploadResults: results,
        editableWikitexts: { ...state.editableWikitexts, ...editableWikitexts },
        pendingTasks: {},
        loading: false,
        showResult: true,
      };
    }
    case "UPLOAD_ASYNC_START": {
      const { tasks, initialResults } = action.payload;
      return {
        ...state,
        pendingTasks: tasks,
        uploadResults: initialResults,
        showResult: true,
      };
    }
    case "UPDATE_UPLOAD_RESULT": {
      const { lang, result } = action.payload;
      return {
        ...state,
        uploadResults: {
          ...state.uploadResults,
          [lang]: result,
        },
      };
    }
    case "SET_PENDING_TASKS":
      return { ...state, pendingTasks: action.payload };
    case "UPDATE_EDITABLE_WIKITEXT": {
      const { lang, text } = action.payload;
      return {
        ...state,
        editableWikitexts: {
          ...state.editableWikitexts,
          [lang]: text,
        },
      };
    }
    case "EDIT_ARTICLE_START":
      return {
        ...state,
        editingState: { ...state.editingState, [action.payload]: true },
        articleEditSuccess: { ...state.articleEditSuccess, [action.payload]: false },
      };
    case "EDIT_ARTICLE_SUCCESS":
      return {
        ...state,
        articleEditSuccess: { ...state.articleEditSuccess, [action.payload]: true },
      };
    case "EDIT_ARTICLE_FAILURE":
      return state;
    case "EDIT_ARTICLE_END":
      return {
        ...state,
        editingState: { ...state.editingState, [action.payload]: false },
      };
    case "INIT_PREFERENCES": {
      const { project, languages, skipUploadSelection } = action.payload;
      return {
        ...state,
        project,
        languages,
        skipUploadSelection,
      };
    }
    default:
      return state;
  }
}
