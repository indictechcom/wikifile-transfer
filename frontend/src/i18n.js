import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {};

function importAll(r) {
  r.keys().forEach((file) => {
    const lang = file.replace('./', '').replace('.json', '');
    resources[lang] = { translation: r(file) };
  });
}

importAll(require.context('./i18n', true, /\.json$/));


i18n.use(initReactI18next).init({
  resources,
  fallbackLng: 'en',
  supportedLngs: Object.keys(resources),
  lng: 'en',
});

export default i18n;