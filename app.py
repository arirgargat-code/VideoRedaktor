import os
import tempfile
import time
from pathlib import Path

import streamlit as st

# Безопасный импорт MoviePy
try:
    from moviepy import VideoFileClip, concatenate_videoclips
except ImportError:
    from moviepy.editor import VideoFileClip, concatenate_videoclips


# ---------------------------------------------------------
# НАСТРОЙКИ
# ---------------------------------------------------------

st.set_page_config(
    page_title="VideoRedactor",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------
# CSS
# ---------------------------------------------------------

st.markdown(
   """
    <style>

    .stApp {
        background-color: #ffffff;
    }

    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 1250px;
    }

    .top-header {
        height: 75px;
        border: 2px solid #222222;
        border-radius: 5px;
        display: flex;
        align-items: center;
        padding: 0 25px;
        margin-bottom: 15px;
        background: #ffffff;
    }

    .logo {
        font-size: 38px;
        font-weight: 700;
        letter-spacing: 2px;
        color: #111111;
    }

    .logo-icon {
        font-size: 32px;
        margin-left: 10px;
    }

    .video-container {
        border: 2px solid #222222;
        min-height: 390px;
        border-radius: 5px;
        display: flex;
        justify-content: center;
        align-items: center;
        background: #fafafa;
        margin-bottom: 15px;
    }

    .video-placeholder {
        text-align: center;
        color: #777777;
        font-size: 22px;
    }

    .timeline {
        border: 2px solid #222222;
        border-radius: 15px;
        padding: 12px 18px;
        margin-top: 10px;
        margin-bottom: 15px;
        background: white;
    }

    .timeline-title {
        display: flex;
        justify-content: space-between;
        font-size: 15px;
        margin-bottom: 8px;
        font-weight: bold;
    }

    .editor-panel {
        border: 2px solid #222222;
        border-radius: 8px;
        padding: 15px;
        margin-top: 15px;
        margin-bottom: 15px;
        background: #ffffff;
    }

    .editor-title {
        font-size: 21px;
        font-weight: 600;
        margin-bottom: 10px;
    }

    .status {
        border: 2px solid #222222;
        border-radius: 15px;
        padding: 10px 20px;
        margin-top: 15px;
        text-align: center;
        font-size: 17px;
    }

    .stButton > button {
        border: 2px solid #222222;
        border-radius: 8px;
        background: white;
        color: black;
        font-weight: 600;
    }

    .stButton > button:hover {
        background: #eeeeee;
        border-color: #000000;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------

if "video_path" not in st.session_state:
    st.session_state.video_path = None

if "video_name" not in st.session_state:
    st.session_state.video_name = None

if "duration" not in st.session_state:
    st.session_state.duration = 0.0

if "trimmed_path" not in st.session_state:
    st.session_state.trimmed_path = None


# ---------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ---------------------------------------------------------


def format_time(seconds: float) -> str:
    """Преобразует секунды в MM:SS."""
    seconds = max(0, int(seconds))
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def load_video(uploaded_file):
    """Сохраняет загруженный файл во временную папку."""
    suffix = Path(uploaded_file.name).suffix
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.write(uploaded_file.getbuffer())
    temp_file.close()
    return temp_file.name


# ---------------------------------------------------------
# ВЫРЕЗАНИЕ ФРАГМЕНТА
# ---------------------------------------------------------


def trim_video_file(source_path, output_path, cut_start, cut_end):
    clip = None
    first_part = None
    second_part = None
    final_clip = None

    try:
        clip = VideoFileClip(source_path)
        duration = float(clip.duration)

        cut_start = max(0.0, min(float(cut_start), duration))
        cut_end = max(0.0, min(float(cut_end), duration))

        if cut_start >= cut_end:
            raise ValueError(
                "Начало вырезаемого участка должно быть меньше конца."
            )

        if cut_start <= 0 and cut_end >= duration:
            raise ValueError("Нельзя удалить всё видео.")

        def make_subclip(c, start, end):
            if hasattr(c, "subclipped"):
                return c.subclipped(start, end)
            return c.subclip(start, end)

        if cut_start > 0:
            first_part = make_subclip(clip, 0, cut_start)

        if cut_end < duration:
            second_part = make_subclip(clip, cut_end, duration)

        parts = [p for p in [first_part, second_part] if p is not None]

        if not parts:
            raise ValueError("После удаления не осталось видео.")

        if len(parts) == 1:
            final_clip = parts[0]
        else:
            final_clip = concatenate_videoclips(parts)

        has_audio = getattr(final_clip, "audio", None) is not None

        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac" if has_audio else None,
            preset="ultrafast",
            fps=getattr(clip, "fps", 24) or 24,
            logger=None,
        )

    finally:
        for c in [final_clip, first_part, second_part, clip]:
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass


# ---------------------------------------------------------
# ИЗМЕНЕНИЕ ГРОМКОСТИ
# ---------------------------------------------------------


def adjust_video_volume(source_path, output_path, volume_level):
    clip = None
    final_clip = None

    try:
        clip = VideoFileClip(source_path)
        factor = volume_level / 100.0

        if factor == 0:
            if hasattr(clip, "without_audio"):
                final_clip = clip.without_audio()
            else:
                final_clip = clip
                final_clip.audio = None
        else:
            if getattr(clip, "audio", None) is not None:
                if hasattr(clip, "with_volume_scaling"):
                    final_clip = clip.with_volume_scaling(factor)
                elif hasattr(clip, "volumex"):
                    final_clip = clip.volumex(factor)
                elif hasattr(clip.audio, "with_volume_scaling"):
                    final_clip = clip
                    final_clip.audio = clip.audio.with_volume_scaling(factor)
                elif hasattr(clip.audio, "volumex"):
                    final_clip = clip
                    final_clip.audio = clip.audio.volumex(factor)
                else:
                    final_clip = clip
            else:
                final_clip = clip

        has_audio = (
            factor > 0 and getattr(final_clip, "audio", None) is not None
        )

        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac" if has_audio else None,
            preset="ultrafast",
            fps=getattr(clip, "fps", 24) or 24,
            logger=None,
        )

    finally:
        for c in [final_clip, clip]:
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass


# ---------------------------------------------------------
# ШАПКА
# ---------------------------------------------------------

st.markdown(
    """
    <div class="top-header">
        <div class="logo">VIDEO</div>
        <div class="logo-icon">🎬</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# ЗАГРУЗКА ВИДЕО
# ---------------------------------------------------------

uploaded_file = st.file_uploader(
    "Загрузить видео", type=["mp4", "mov", "avi", "mkv", "webm"]
)

if uploaded_file is not None:
    if st.session_state.video_name != uploaded_file.name:
        try:
            video_path = load_video(uploaded_file)
            clip = VideoFileClip(video_path)

            st.session_state.video_path = video_path
            st.session_state.video_name = uploaded_file.name
            st.session_state.duration = float(clip.duration)
            st.session_state.trimmed_path = None

            clip.close()

        except Exception as error:
            st.error(f"Не удалось открыть видео: {error}")


# ---------------------------------------------------------
# ЕСЛИ ВИДЕО НЕ ЗАГРУЖЕНО
# ---------------------------------------------------------

if st.session_state.video_path is None:
    st.markdown(
        """
        <div class="video-container">
            <div class="video-placeholder">
                🎥<br>
                Загрузите видео для начала работы
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Поддерживаются MP4, MOV, AVI, MKV и WEBM.")
    st.stop()


# ---------------------------------------------------------
# ОСНОВНЫЕ ДАННЫЕ И ПРЕДПРОСМОТР
# ---------------------------------------------------------

video_path = st.session_state.video_path
duration = st.session_state.duration

active_video = (
    st.session_state.trimmed_path
    if st.session_state.trimmed_path
    else video_path
)

st.markdown(
    '<div class="editor-title">Предпросмотр</div>', unsafe_allow_html=True
)
st.video(active_video)


# ---------------------------------------------------------
# ПАНЕЛЬ РЕДАКТИРОВАНИЯ
# ---------------------------------------------------------

st.markdown(
    """
    <div class="editor-panel">
        <div class="editor-title">
            Редактирование
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2)

# =========================================================
# ОБРЕЗКА
# =========================================================

with col1:
    st.subheader("✂️ Удаление фрагмента")
    st.caption(
        "Перетащите левый и правый маркеры. Выбранный участок будет ВЫРЕЗАН из видео."
    )

    time_range = st.slider(
        "Фрагмент для удаления:",
        min_value=0.0,
        max_value=float(round(duration, 2)),
        value=(
            float(round(duration / 3, 2)),
            float(round(duration * 2 / 3, 2)),
        ),
        step=0.1,
        format="%.1f сек.",
    )

    cut_start, cut_end = time_range

    if duration > 0:
        cut_start_pct = cut_start / duration * 100
        cut_width_pct = (cut_end - cut_start) / duration * 100
    else:
        cut_start_pct = 0
        cut_width_pct = 0

    timeline_html = f"""
    <div class="timeline">
        <div class="timeline-title">
            <span style="color:#ff2222; font-weight:600;">
                ✂️ БУДЕТ ВЫРЕЗАНО
            </span>
            <span>
                {format_time(cut_start)} — {format_time(cut_end)}
            </span>
        </div>
        <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:12px; color:#777;">
            <span>00:00</span>
            <span>{format_time(duration)}</span>
        </div>
        <div style="height:24px; background:#55c878; border-radius:12px; position:relative; overflow:hidden; border:1px solid #aaa;">
            <div style="position:absolute; left:{cut_start_pct:.2f}%; top:0; height:100%; width:{cut_width_pct:.2f}%; background:#ff3333;"></div>
        </div>
        <div style="display:flex; justify-content:center; gap:20px; margin-top:8px; font-size:13px;">
            <span style="color:#55a866;">🟢 Останется</span>
            <span style="color:#dd2222; font-weight:600;">🔴 Будет удалено</span>
        </div>
    </div>
    """

    st.markdown(timeline_html, unsafe_allow_html=True)

    cut_duration = cut_end - cut_start
    remaining_duration = duration - cut_duration

    info_col1, info_col2 = st.columns(2)

    with info_col1:
        st.metric("✂ Будет удалено", format_time(cut_duration))

    with info_col2:
        st.metric("⏱ Останется", format_time(remaining_duration))

    trim_button = st.button(
        "✂️ УДАЛИТЬ ВЫБРАННЫЙ ФРАГМЕНТ", use_container_width=True
    )

    if trim_button:
        if cut_start >= cut_end:
            st.error("Время начала должно быть меньше времени окончания.")
        elif cut_start <= 0 and cut_end >= duration:
            st.error(
                "Нельзя удалить всё видео. Оставьте хотя бы часть видео."
            )
        else:
            os.makedirs("temp_trim", exist_ok=True)
            timestamp = int(time.time())
            trim_path = os.path.join("temp_trim", f"trimmed_{timestamp}.mp4")

            with st.spinner("Удаляю выбранный фрагмент..."):
                try:
                    trim_video_file(
                        active_video, trim_path, cut_start, cut_end
                    )

                    new_clip = VideoFileClip(trim_path)
                    new_duration = float(new_clip.duration)
                    new_clip.close()

                    st.session_state.trimmed_path = trim_path
                    st.session_state.duration = new_duration

                    st.success(
                        f"Фрагмент {format_time(cut_start)} — {format_time(cut_end)} удалён!"
                    )
                    st.rerun()

                except Exception as error:
                    st.error(f"Ошибка при удалении фрагмента: {error}")


# =========================================================
# АУДИО (НАСТРОЙКА ГРОМКОСТИ)
# =========================================================

with col2:
    st.subheader("🔊 Изменить громкость")

    st.caption("Установите нужный уровень громкости (0% — без звука).")

    volume_level = st.slider(
        "Уровень громкости (%)",
        min_value=0,
        max_value=200,
        value=100,
        step=5,
        format="%d%%",
    )

    volume_button = st.button("🔊 ПРИМЕНИТЬ ГРОМКОСТЬ", use_container_width=True)

    if volume_button:
        os.makedirs("temp_trim", exist_ok=True)
        timestamp = int(time.time())
        vol_path = os.path.join("temp_trim", f"volume_{timestamp}.mp4")

        with st.spinner("Применяю громкость..."):
            try:
                # Берём активное видео
                source_vid = (
                    st.session_state.trimmed_path
                    if st.session_state.trimmed_path
                    else st.session_state.video_path
                )

                adjust_video_volume(source_vid, vol_path, volume_level)

                st.session_state.trimmed_path = vol_path

                st.success(f"Громкость изменена на {volume_level}%!")
                st.rerun()

            except Exception as error:
                st.error(f"Ошибка при изменении громкости: {error}")

# ---------------------------------------------------------
# СТАТУС
# ---------------------------------------------------------

st.markdown(
    """
    <div class="status">
        Статус: приложение готово к работе
    </div>
    """,
    unsafe_allow_html=True,
)