// Content script MV3 не может быть ES-модулем: загружаем модуль динамически.
import(chrome.runtime.getURL("content.js"));
