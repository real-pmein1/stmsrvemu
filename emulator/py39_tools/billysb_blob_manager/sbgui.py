# NEVER USE IMPORT, ALWAYS USE
# from MODULE import OBJ
# IT IS MORE EFFICIENT AND RESULTS IN SMALLER FILE SIZES

from PyQt5.QtWidgets import (
    QWidget, QPushButton, QCheckBox, QRadioButton, QLineEdit, QTextEdit, QLabel, QFrame,
    QScrollBar, QStyleOptionSlider, QMainWindow, QSizePolicy,
    QDialog, QVBoxLayout, QHBoxLayout, QStyleOptionButton, QStyle
)
from PyQt5.QtGui import QPixmap, QPainter, QFont, QBrush, QColor, QLinearGradient, QIcon, QFontMetricsF, QPen, QPainterPath, QRegion
from PyQt5.QtCore import Qt, QRect, QEvent, QSize
from os.path import join as _pjoin
import os, sys

def _res_join(*parts: str) -> str:
    """
    Find resources in both dev and frozen builds.

    Search order:
    1) PyInstaller temp dir (sys._MEIPASS)      -> e.g. .../_MEIPASS/resources/...
    2) Next to the executable (frozen build)    -> e.g. <exe dir>/resources/...
    3) Next to this source file (dev run)       -> e.g. <repo dir>/resources/...

    Returns the first existing path; otherwise falls back to dev path.
    """
    cands = []

    # 1) PyInstaller bundle
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cands.append(os.path.join(meipass, *parts))

    # 2) Folder next to the exe (useful if you ship "resources" alongside .exe)
    try:
        exe_dir = os.path.dirname(sys.executable)
        cands.append(os.path.join(exe_dir, *parts))
    except Exception:
        pass

    # 3) Source file directory (dev)
    here = os.path.dirname(os.path.abspath(__file__))
    cands.append(os.path.join(here, *parts))

    for p in cands:
        if os.path.exists(p):
            return p

    # If nothing exists yet (e.g., during packaging), default to dev path
    return os.path.join(here, *parts)

# Override the earlier alias so all existing _pjoin('resources', ...) calls use this resolver
_pjoin = _res_join


def _as_url(path: str) -> str:
    """
    Convert a filesystem path to a QSS-safe file URL.
    Works on Windows & POSIX. Always forward-slashes.
    """
    # Absolute path is required for QSS url(...)
    abspath = os.path.abspath(path)
    # Normalize to forward slashes and add file:///
    return "file:///" + abspath.replace("\\", "/")

# NEVER USE IMPORT, ALWAYS USE
# from MODULE import OBJ
# IT IS MORE EFFICIENT AND RESULTS IN SMALLER FILE SIZES
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtCore import QRect


STEAM_LINE_DARK = "#292e23"   # separator dark
STEAM_LINE_LITE = "#808080"   # optional highlight (for subtle bevel)


class ImageCheckBox(QCheckBox):
    def __init__(self, text='', parent=None, size=20, font_family="Tahoma", font_pt=9, bold=True):
        super(ImageCheckBox, self).__init__(text, parent)
        self._indicator_size = int(size)

        # set font
        font = QFont(font_family, font_pt)
        font.setBold(bold)
        self.setFont(font)

        # set stylesheet
        self.setStyleSheet(self._generate_stylesheet())

        # make icon/indicator size consistent
        self.setIconSize(QSize(self._indicator_size, self._indicator_size))
    def paintEvent(self, e):
        # Let the label text layout first
        super(ImageCheckBox, self).paintEvent(e)
    
        # Compute indicator rect the way Qt does
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        ind_rect = self.style().subElementRect(QStyle.SE_CheckBoxIndicator, opt, self)
    
        # Choose pixmap by state
        if not self.isEnabled():
            pm = QPixmap(_pjoin('resources', 'p_check_disabled_selected.tga' if self.isChecked() else 'p_check_disabled.tga'))
        else:
            if self.isDown():
                pm = QPixmap(_pjoin('resources', 'p_check_mousedown.tga'))
            else:
                pm = QPixmap(_pjoin('resources', 'p_check_selected.tga' if self.isChecked() else 'p_check.tga'))
    
        if not pm.isNull():
            # Center the pixmap inside the indicator rect, scaling to indicator size if needed
            size = self._indicator_size
            pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = ind_rect.x() + (ind_rect.width() - pm.width()) // 2
            y = ind_rect.y() + (ind_rect.height() - pm.height()) // 2
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(x, y, pm)
            painter.end()
    def _generate_stylesheet(self):
        # Resolve to absolute paths then to file URLs
        unchecked_path         = _pjoin('resources', 'p_check.tga')
        checked_path           = _pjoin('resources', 'p_check_selected.tga')
        disabled_path          = _pjoin('resources', 'p_check_disabled.tga')
        disabled_checked_path  = _pjoin('resources', 'p_check_disabled_selected.tga')
        pressed_path           = _pjoin('resources', 'p_check_mousedown.tga')
    
        def _url(p):
            abspath = os.path.abspath(p).replace("\\", "/")
            return f'file:///{abspath}'
    
        unchecked_url        = _url(unchecked_path)
        checked_url          = _url(checked_path)
        disabled_url         = _url(disabled_path)
        disabled_checked_url = _url(disabled_checked_path)
        pressed_url          = _url(pressed_path)
    
        size = self._indicator_size
        # NOTE: we set BOTH `image:` and `border-image:`; whichever your Qt prefers will work.
        # The quotes around the URLs are important.
        return f"""
        QCheckBox {{
            color: #d5dbcf;
            spacing: 5px;
        }}
        QCheckBox::indicator {{
            width: {size}px;
            height: {size}px;
            background: transparent;
            border: none;
            /* fallback bg to help debug: */
            /* background-color: rgba(255,0,0,20%); */
        }}
        QCheckBox::indicator:unchecked {{
            image: url("{unchecked_url}");
            border-image: url("{unchecked_url}") 0 0 0 0 stretch stretch;
        }}
        QCheckBox::indicator:checked {{
            image: url("{checked_url}");
            border-image: url("{checked_url}") 0 0 0 0 stretch stretch;
        }}
        QCheckBox::indicator:pressed {{
            image: url("{pressed_url}");
            border-image: url("{pressed_url}") 0 0 0 0 stretch stretch;
        }}
        QCheckBox::indicator:disabled {{
            image: url("{disabled_url}");
            border-image: url("{disabled_url}") 0 0 0 0 stretch stretch;
        }}
        QCheckBox::indicator:disabled:checked {{
            image: url("{disabled_checked_url}");
            border-image: url("{disabled_checked_url}") 0 0 0 0 stretch stretch;
        }}
        """.strip()


class ImageRadioButton(QRadioButton):
    def __init__(self, text='', parent=None, size=14, font_family="Tahoma", font_pt=9, bold=True):
        super(ImageRadioButton, self).__init__(text, parent)
        self._indicator_size = int(size)

        font = QFont(font_family, font_pt)
        font.setBold(bold)
        self.setFont(font)
        self.setIconSize(QSize(self._indicator_size, self._indicator_size))
        self.setStyleSheet(self._generate_stylesheet())

    def paintEvent(self, e):
        super(ImageRadioButton, self).paintEvent(e)

        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        ind_rect = self.style().subElementRect(QStyle.SE_RadioButtonIndicator, opt, self)

        if not self.isEnabled():
            pm = QPixmap(_pjoin('resources', 'p_radio_disabled_selected.tga' if self.isChecked() else 'p_radio_disabled.tga'))
        elif self.isDown():
            pm = QPixmap(_pjoin('resources', 'p_radio_mousedown.tga'))
        else:
            pm = QPixmap(_pjoin('resources', 'p_radio_selected.tga' if self.isChecked() else 'p_radio.tga'))

        if not pm.isNull():
            size = self._indicator_size
            pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = ind_rect.x() + (ind_rect.width() - pm.width()) // 2
            y = ind_rect.y() + (ind_rect.height() - pm.height()) // 2
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(x, y, pm)
            painter.end()

    def _generate_stylesheet(self):
        def _url(name):
            abspath = os.path.abspath(_pjoin('resources', name)).replace("\\", "/")
            return f'file:///{abspath}'

        unchecked_url = _url('p_radio.tga')
        checked_url = _url('p_radio_selected.tga')
        disabled_url = _url('p_radio_disabled.tga')
        disabled_checked_url = _url('p_radio_disabled_selected.tga')
        pressed_url = _url('p_radio_mousedown.tga')
        size = self._indicator_size

        return f"""
        QRadioButton {{
            color: #d5dbcf;
            spacing: 5px;
        }}
        QRadioButton::indicator {{
            width: {size}px;
            height: {size}px;
            background: transparent;
            border: none;
        }}
        QRadioButton::indicator:unchecked {{
            image: url("{unchecked_url}");
            border-image: url("{unchecked_url}") 0 0 0 0 stretch stretch;
        }}
        QRadioButton::indicator:checked {{
            image: url("{checked_url}");
            border-image: url("{checked_url}") 0 0 0 0 stretch stretch;
        }}
        QRadioButton::indicator:pressed {{
            image: url("{pressed_url}");
            border-image: url("{pressed_url}") 0 0 0 0 stretch stretch;
        }}
        QRadioButton::indicator:disabled {{
            image: url("{disabled_url}");
            border-image: url("{disabled_url}") 0 0 0 0 stretch stretch;
        }}
        QRadioButton::indicator:disabled:checked {{
            image: url("{disabled_checked_url}");
            border-image: url("{disabled_checked_url}") 0 0 0 0 stretch stretch;
        }}
        """.strip()


class SteamSeparator(QWidget):
    """
    Steam-style bevel:
    • 1px dark horizontal line at the top
    • 1px light line directly below (bevel)
    • plus 1px light column on the far right
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dark = QColor(STEAM_LINE_DARK)
        self._light = QColor(STEAM_LINE_LITE)
        self.setMinimumHeight(2)  # need room for dark+light rows
        self.setMaximumHeight(2)
        self.setAttribute(Qt.WA_StyledBackground, False)

    def sizeHint(self):
        return QSize(10, 2)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        w = self.width()

        # Dark horizontal line (row 0)
        p.fillRect(0, 0, w, 1, self._dark)

        # Light horizontal line (row 1)
        p.fillRect(0, 1, w, 1, self._light)

        # Light vertical highlight at far right (covers both rows)
        p.fillRect(w - 1, 0, 1, 2, self._light)
        p.end()


class NineSliceButton(QPushButton):
    """
    QPushButton subclass that draws a 9-slice skin and then paints the label
    ON TOP of everything so the text never gets hidden/clipped by the chrome.
    No geometry/size math is changed from your original – only the draw order.
    """
    def __init__(self, text, base_name="p_button", parent=None):
        super().__init__(text, parent)
        self.base = base_name
        self.state = 'default'
        self.style_override = None  # e.g. 'normal'
        self._load_pixmaps()
        self.setMouseTracking(True)
        self.setFont(QFont('Arial', 11))
        self.setMinimumSize(50, 24)

    # ---------- assets ----------
    def _load_pixmaps(self):
        self.slices = {}
        for state in ['default', 'normal', 'mouseover', 'mousedown', 'disabled']:
            if state == 'normal':
                prefix = f"{self.base}_b"
            elif state == 'default':
                prefix = self.base
            else:
                prefix = f"{self.base}_{state}"
            parts = ['tl','t','tr','l','c','r','bl','b','br']
            d = {}
            for p in parts:
                d[p] = QPixmap(_pjoin('resources', f"{prefix}_{p}.tga"))
            self.slices[state] = d

    def _maps_for_state(self):
        current_state = self.style_override or self.state
        return self.slices.get(current_state, self.slices['default'])

    # ---------- state / events ----------
    def setDisabled(self, a0):
        self.state = 'disabled'
        self.update()
        super().setDisabled(a0)

    def setStyle(self, style_name):
        if style_name in self.slices:
            self.style_override = style_name
            self.update()

    def clearStyle(self):
        self.style_override = None
        self.update()

    def enterEvent(self, e):
        if not self.isEnabled() or self.style_override == 'disabled':
            return
        self.state = 'mouseover'
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not self.isEnabled() or self.style_override == 'disabled':
            return
        self.state = 'default'
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.isEnabled() and self.style_override != 'disabled':
            self.state = 'mousedown'
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if self.style_override not in ['disabled', 'normal']:
            self.state = 'mouseover' if self.rect().contains(e.pos()) else 'default'
            self.update()
        super().mouseReleaseEvent(e)

    # ---------- painting (text drawn LAST) ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing, False)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        s = self._maps_for_state()

        tl, tr, bl, br = s['tl'], s['tr'], s['bl'], s['br']
        t, b, l_, r_    = s['t'], s['b'], s['l'], s['r']
        c_              = s.get('c')

        # Corners
        if not tl.isNull(): p.drawPixmap(0, 0, tl)
        if not tr.isNull(): p.drawPixmap(w - tr.width(), 0, tr)
        if not bl.isNull(): p.drawPixmap(0, h - bl.height(), bl)
        if not br.isNull(): p.drawPixmap(w - br.width(), h - br.height(), br)

        # Edges (scaled to fit, same behavior as your original)
        if not t.isNull():
            top_rect = QRect(tl.width(), 0, max(0, w - tl.width() - tr.width()), t.height())
            p.drawPixmap(top_rect, t.scaled(top_rect.size()))
        if not b.isNull():
            bottom_rect = QRect(bl.width(), h - b.height(), max(0, w - bl.width() - br.width()), b.height())
            p.drawPixmap(bottom_rect, b.scaled(bottom_rect.size()))
        if not l_.isNull():
            left_rect = QRect(0, tl.height(), l_.width(), max(0, h - tl.height() - bl.height()))
            p.drawPixmap(left_rect, l_.scaled(left_rect.size()))
        if not r_.isNull():
            right_rect = QRect(w - r_.width(), tr.height(), r_.width(), max(0, h - tr.height() - br.height()))
            p.drawPixmap(right_rect, r_.scaled(right_rect.size()))

        # Center (fill or center image)
        cx, cy = tl.width(), tl.height()
        cw = max(0, w - tl.width() - tr.width())
        ch = max(0, h - tl.height() - bl.height())

        if c_ and not c_.isNull():
            p.drawPixmap(QRect(cx, cy, cw, ch), c_.scaled(cw, ch))
        else:
            # same palettes you had
            if self.style_override == 'normal':
                mid = {'default':'#5a5c55','mouseover':'#a0a055','mousedown':'#505250','disabled':'#686a65'}
                tex = {'default':'#ffffff','mouseover':'#ffff88','mousedown':'#c4b550','disabled':'#858585'}
            else:
                mid = {'default':'#686a65','mouseover':'#7b7a79','mousedown':'#5d5e5c','disabled':'#686a65'}
                tex = {'default':'#ffffff','mouseover':'#c4b550','mousedown':'#c4b550','disabled':'#858585'}
            state = self.style_override or self.state
            p.fillRect(QRect(cx, cy, cw, ch), QColor(mid.get(state, '#686a65')))

        # ---- TEXT LAST (draw over the skin; not clipped to center) ----
        state = self.style_override or self.state
        if self.style_override == 'normal':
            pen_map = {'default':'#ffffff','mouseover':'#ffff88','mousedown':'#c4b550','disabled':'#858585'}
        else:
            pen_map = {'default':'#ffffff','mouseover':'#c4b550','mousedown':'#c4b550','disabled':'#858585'}

        p.setPen(QColor(pen_map.get(state, '#ffffff')))
        p.setFont(self.font())

        # Use full widget rect so small center areas don't crop the label
        p.drawText(self.rect(), Qt.AlignCenter, self.text())

        # IMPORTANT: do not call super().paintEvent() after drawing text,
        # or the default style may overpaint the label.
        # If you ever need native focus cues, you can call super().paintEvent(event)
        # at the VERY START of this method instead, before custom painting.
        # super().paintEvent(event)  # intentionally omitted


class NineSliceLineEdit(QLineEdit):
    """
    QLineEdit with a scalable 9-slice background (tl, t, tr, l, c, r, bl, b, br)
    that respects high-DPI and plays nicely with layouts.

    Resource naming convention (under ./resources):
      <base>_tl.tga, <base>_t.tga, <base>_tr.tga, <base>_l.tga, <base>_c.tga,
      <base>_r.tga, <base>_bl.tga, <base>_b.tga, <base>_br.tga

    Example: base_name="combo" → resources/combo_tl.tga, ...
    """
    def __init__(self, parent=None, base_name="combo", *,
                 pad_top=3, pad_bottom=3, min_pix=28, center_fill='#444d3e',
                 font_family="Tahoma", font_pt=9, font_bold=False,
                 text_color="#ffffff", placeholder_color="#c0c0c0"):
        super().__init__(parent)
        self.base = str(base_name)
        self.state = 'default'
        self.setMouseTracking(True)
        self.setFrame(False)

        # padding + minimum pixel height
        self._pad_top = int(pad_top)
        self._pad_bottom = int(pad_bottom)
        self._min_pix = int(min_pix)
        self._center_fill = QColor(center_fill)

        # --- font ---
        f = QFont(font_family, font_pt)
        f.setBold(font_bold)
        self.setFont(f)

        # --- text colors ---
        self.setStyleSheet(
            f"""
            QLineEdit {{
                color: {text_color};
                background-color: transparent;
            }}
            QLineEdit::placeholder {{
                color: {placeholder_color};
            }}
            """
        )

        # slices + margins
        self.slices = {}
        self._load_pixmaps()
        left_w = self._logical_width(self.slices.get('l'))
        right_w = self._logical_width(self.slices.get('r'))
        self.setTextMargins(max(5, left_w + 2), self._pad_top,
                            max(5, right_w + 2), self._pad_bottom)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(self._calc_height())
        if hasattr(Qt, "WA_HighDpiPixmaps"):
            self.setAttribute(Qt.WA_HighDpiPixmaps, True)

    # ---------- Sizing helpers ----------
    def _device_pixel_ratio(self) -> float:
        try:
            return float(self.devicePixelRatioF())
        except Exception:
            return 1.0

    def _logical_width(self, pm: QPixmap) -> int:
        if not isinstance(pm, QPixmap) or pm.isNull():
            return 0
        dpr = pm.devicePixelRatio() or 1.0
        return int(pm.width() / dpr)

    def _logical_height(self, pm: QPixmap) -> int:
        if not isinstance(pm, QPixmap) or pm.isNull():
            return 0
        dpr = pm.devicePixelRatio() or 1.0
        return int(pm.height() / dpr)

    def _calc_height(self) -> int:
        fm = QFontMetricsF(self.font())
        text_h = int(fm.height())
        top_h = self._logical_height(self.slices.get('t'))
        bot_h = self._logical_height(self.slices.get('b'))
        # enough for text + pads, and not less than cap height
        return max(
            text_h + self._pad_top + self._pad_bottom + 4,
            max(top_h, bot_h) + 6,
            self._min_pix
        )

    def minimumSizeHint(self) -> QSize:
        return QSize(120, self._calc_height())

    def sizeHint(self) -> QSize:
        fm = QFontMetricsF(self.font())
        l, t, r, b = self.getTextMargins()
        # room for ~24 chars + margins
        w = int(fm.horizontalAdvance("X" * 24)) + l + r + 8
        return QSize(max(180, w), self._calc_height())

    # ---------- Assets ----------
    def _load_pixmaps(self):
        """
        Load 9-slice images and register the current DPR so Qt scales them crisply.
        Safe to call again when DPR changes.
        """
        parts = ['tl', 't', 'tr', 'l', 'c', 'r', 'bl', 'b', 'br']
        dpr = self._device_pixel_ratio()
        base = self.base

        new_slices = {}
        for p in parts:
            fname = _pjoin('resources', f"{base}_{p}.tga")
            pm = QPixmap(fname)
            if not pm.isNull():
                # Let Qt know these pixels are for a specific DPR
                try:
                    pm.setDevicePixelRatio(dpr)
                except Exception:
                    pass
            new_slices[p] = pm

        self.slices = new_slices

        # refresh margins & min height
        left_w = self._logical_width(self.slices.get('l'))
        right_w = self._logical_width(self.slices.get('r'))
        self.setTextMargins(max(5, left_w + 2), self._pad_top,
                            max(5, right_w + 2), self._pad_bottom)
        self.setMinimumHeight(self._calc_height())

    # ---------- State changes ----------
    def setDisabled(self, disable):
        self.state = 'disabled' if disable else 'default'
        super().setDisabled(disable)
        self.update()

    def enterEvent(self, ev):
        if self.isEnabled():
            self.state = 'mouseover'
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        if self.isEnabled():
            self.state = 'default'
        super().leaveEvent(ev)

    def focusInEvent(self, ev):
        if self.isEnabled():
            self.state = 'mousedown'
        super().focusInEvent(ev)

    def focusOutEvent(self, ev):
        if self.isEnabled():
            self.state = 'default'
        super().focusOutEvent(ev)

    # React to HiDPI changes safely
    def event(self, ev):
        if hasattr(QEvent, "DevicePixelRatioChange") and ev.type() == QEvent.DevicePixelRatioChange:
            self._load_pixmaps()
            self.update()
        return super().event(ev)

    # ---------- Painting ----------
    def _have_all_slices(self) -> bool:
        # For a clean 9-slice we need at least all corners + edges.
        needed = ('tl', 't', 'tr', 'l', 'r', 'bl', 'b', 'br')
        return all(isinstance(self.slices.get(k), QPixmap) and not self.slices[k].isNull() for k in needed)

    def _paint_fallback(self, p: QPainter, w: int, h: int):
        """ If slices are missing, draw a rounded rect fallback (so nothing clips). """
        radius = 6
        rect_pen = QPen(QColor(0, 0, 0, 180), 1.2)
        p.setPen(rect_pen)
        p.setBrush(QBrush(self._center_fill))
        p.setRenderHint(QPainter.Antialiasing, True)
        p.drawRoundedRect(0.5, 0.5, w - 1.0, h - 1.0, radius, radius)

    def paintEvent(self, ev):
        w, h = self.width(), self.height()
        p = QPainter(self)
        # nicer scaled-pixmap transforms
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if self._have_all_slices():
            s = self.slices

            # logical sizes
            tl_w = self._logical_width(s['tl']); tl_h = self._logical_height(s['tl'])
            tr_w = self._logical_width(s['tr']); tr_h = self._logical_height(s['tr'])
            bl_w = self._logical_width(s['bl']); bl_h = self._logical_height(s['bl'])
            br_w = self._logical_width(s['br']); br_h = self._logical_height(s['br'])

            # corners
            p.drawPixmap(QRect(0, 0, tl_w, tl_h), s['tl'])
            p.drawPixmap(QRect(w - tr_w, 0, tr_w, tr_h), s['tr'])
            p.drawPixmap(QRect(0, h - bl_h, bl_w, bl_h), s['bl'])
            p.drawPixmap(QRect(w - br_w, h - br_h, br_w, br_h), s['br'])

            # edges
            top_h = self._logical_height(s.get('t'))
            bot_h = self._logical_height(s.get('b'))
            left_w = self._logical_width(s.get('l'))
            right_w = self._logical_width(s.get('r'))

            if top_h > 0:
                p.drawPixmap(QRect(tl_w, 0, max(0, w - tl_w - tr_w), top_h), s['t'])
            if bot_h > 0:
                p.drawPixmap(QRect(bl_w, h - bot_h, max(0, w - bl_w - br_w), bot_h), s['b'])
            if left_w > 0:
                p.drawPixmap(QRect(0, tl_h, left_w, max(0, h - tl_h - bl_h)), s['l'])
            if right_w > 0:
                p.drawPixmap(QRect(w - right_w, tr_h, right_w, max(0, h - tr_h - br_h)), s['r'])

            # center fill (can be replaced with a tiled center pixmap 'c' if you have one)
            cx, cy = tl_w, tl_h
            cw = max(0, w - tl_w - tr_w)
            ch = max(0, h - tl_h - bl_h)
            if cw > 0 and ch > 0:
                p.fillRect(cx, cy, cw, ch, self._center_fill)
        else:
            # Missing assets → draw a safe fallback
            self._paint_fallback(p, w, h)

        p.end()
        # draw text & cursor on top
        super().paintEvent(ev)


class NineSliceScrollBar(QScrollBar):
    """
    Custom scrollbar with nine-slice background images.

    Expected image structure:
      - scroll_btn_top.tga / scroll_btn_bottom.tga (arrow buttons)
      - scroll_handle_tl.tga, scroll_handle_t.tga, scroll_handle_tr.tga (handle top)
      - scroll_handle_l.tga, scroll_handle_r.tga (handle sides)
      - scroll_handle_bl.tga, scroll_handle_b.tga, scroll_handle_br.tga (handle bottom)
      - scroll_track.tga (background track - optional)
    """
    def __init__(self, orientation=Qt.Vertical, parent=None):
        super().__init__(orientation, parent)
        self.orientation = orientation
        self._load_pixmaps()
        self.setStyleSheet("QScrollBar { background: transparent; }")

        # Track mouse for hover effects
        self.setMouseTracking(True)
        self._hover_handle = False
        self._hover_up_btn = False
        self._hover_down_btn = False

    def _load_pixmaps(self):
        """Load all scrollbar images"""
        self.images = {}

        # Button images
        for btn in ['btn_top', 'btn_bottom']:
            fname = _pjoin('resources', f"scroll_{btn}.tga")
            self.images[btn] = QPixmap(fname)

        # Handle nine-slice images
        handle_parts = ['tl', 't', 'tr', 'l', 'r', 'bl', 'b', 'br']
        for part in handle_parts:
            fname = _pjoin('resources', f"scroll_handle_{part}.tga")
            self.images[f'handle_{part}'] = QPixmap(fname)

        # Optional track background
        track_fname = _pjoin('resources', "scroll_track.tga")
        self.images['track'] = QPixmap(track_fname)

    def paintEvent(self, event):
        painter = QPainter(self)
        #painter.setRenderHint(QPainter.Antialiasing)

        # Get scrollbar metrics
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        rect = self.rect()

        # FIXME: Need to implement a border around the scroll area.

        # Draw track background if available
        if 'track' in self.images:
            painter.drawPixmap(rect, self.images['track'].scaled(rect.size()))

        # Calculate button and handle rectangles
        btn_size = 16  # Adjust based on your button image size
        if self.orientation == Qt.Vertical:
            # Top button
            top_btn_rect = QRect(0, 0, rect.width(), btn_size)
            # Bottom button
            bottom_btn_rect = QRect(0, rect.height() - btn_size, rect.width(), btn_size)
            # Handle area
            handle_area = QRect(0, btn_size, rect.width(), rect.height() - 2 * btn_size)
        else:
            # Left button
            top_btn_rect = QRect(0, 0, btn_size, rect.height())
            # Right button
            bottom_btn_rect = QRect(rect.width() - btn_size, 0, btn_size, rect.height())
            # Handle area
            handle_area = QRect(btn_size, 0, rect.width() - 2 * btn_size, rect.height())

        # Draw buttons
        if 'btn_top' in self.images:
            painter.drawPixmap(top_btn_rect, self.images['btn_top'].scaled(top_btn_rect.size()))
        if 'btn_bottom' in self.images:
            painter.drawPixmap(bottom_btn_rect, self.images['btn_bottom'].scaled(bottom_btn_rect.size()))

        # Calculate handle position and size
        handle_rect = self._calculate_handle_rect(handle_area)

        # Draw nine-slice handle
        self._draw_nine_slice_handle(painter, handle_rect)

    def _calculate_handle_rect(self, handle_area):
        """Calculate the position and size of the scroll handle"""
        if self.maximum() == 0:
            return handle_area

        # Calculate handle size based on page step
        if self.orientation == Qt.Vertical:
            handle_length = max(20, int(handle_area.height() * self.pageStep() / (self.maximum() + self.pageStep())))
            handle_pos = int(handle_area.top() + (handle_area.height() - handle_length) * self.value() / self.maximum())
            return QRect(handle_area.left(), handle_pos, handle_area.width(), handle_length)
        else:
            handle_length = max(20, int(handle_area.width() * self.pageStep() / (self.maximum() + self.pageStep())))
            handle_pos = int(handle_area.left() + (handle_area.width() - handle_length) * self.value() / self.maximum())
            return QRect(handle_pos, handle_area.top(), handle_length, handle_area.height())

    def _draw_nine_slice_handle(self, painter, rect):
        """Draw the scrollbar handle using nine-slice technique"""
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Check if we have all necessary handle images
        required_parts = ['handle_tl', 'handle_t', 'handle_tr', 'handle_l', 'handle_r', 'handle_bl', 'handle_b', 'handle_br']
        if not all(part in self.images for part in required_parts):
            # Fallback to simple rectangle if images missing
            painter.fillRect(rect, QColor(100, 100, 100))
            return

        # Get slice images
        tl = self.images['handle_tl']
        t = self.images['handle_t']
        tr = self.images['handle_tr']
        l = self.images['handle_l']
        r = self.images['handle_r']
        bl = self.images['handle_bl']
        b = self.images['handle_b']
        br = self.images['handle_br']

        # Corner dimensions
        corner_w = tl.width()
        corner_h = tl.height()

        # Ensure handle is large enough for corners
        if rect.width() < 2 * corner_w or rect.height() < 2 * corner_h:
            painter.fillRect(rect, QColor(100, 100, 100))
            return

        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

        # Draw corners
        painter.drawPixmap(x, y, tl)
        painter.drawPixmap(x + w - corner_w, y, tr)
        painter.drawPixmap(x, y + h - corner_h, bl)
        painter.drawPixmap(x + w - corner_w, y + h - corner_h, br)

        # Draw edges
        # Top edge
        top_rect = QRect(x + corner_w, y, w - 2 * corner_w, corner_h)
        painter.drawPixmap(top_rect, t.scaled(top_rect.size()))
        # Bottom edge
        bottom_rect = QRect(x + corner_w, y + h - corner_h, w - 2 * corner_w, corner_h)
        painter.drawPixmap(bottom_rect, b.scaled(bottom_rect.size()))
        # Left edge
        left_rect = QRect(x, y + corner_h, corner_w, h - 2 * corner_h)
        painter.drawPixmap(left_rect, l.scaled(left_rect.size()))
        # Right edge
        right_rect = QRect(x + w - corner_w, y + corner_h, corner_w, h - 2 * corner_h)
        painter.drawPixmap(right_rect, r.scaled(right_rect.size()))

        # Fill center (you could use a center image here if you have one)
        center_rect = QRect(x + corner_w, y + corner_h, w - 2 * corner_w, h - 2 * corner_h)
        painter.fillRect(center_rect, QColor('#686a65'))  # Or use a center image


class NineSliceTextEdit(QTextEdit):
    """
    QTextEdit subclass drawing a scalable 9-slice background with custom scrollbar.
    Expects resources named:
      resources/combo_tl.tga, combo_t.tga … combo_br.tga
      resources/scroll_btn_top.tga, scroll_btn_bottom.tga
      resources/scroll_handle_tl.tga, scroll_handle_t.tga, etc.
    """
    def __init__(self, parent=None, base_name="combo"):
        super().__init__(parent)
        self.base = base_name
        self.state = 'default'
        self.setMouseTracking(True)
        self.NoFrame = True

        self._load_pixmaps()

        # ensure enough height so top/bottom slices don't overlap text
        top_h = self.slices['t'].height()
        bot_h = self.slices['b'].height()
        # add top/bottom margins, plus a bit extra
        self.setViewportMargins(5, top_h - 10, 2, bot_h - 10)

        self.viewport().setAttribute(Qt.WA_TranslucentBackground)
        self.setFrameShape(QFrame.NoFrame)
        self.setFrameShadow(QFrame.Plain)

        # transparent to show our pixmaps underneath
        self.setStyleSheet("""
            QTextEdit {
                color: #ffffff;            /* text color */
                background-color: transparent;
                border: none;              /* extra insurance */
            }
            QTextEdit[placeholderText]:empty:focus {
                color: #ffffff;
            }

            /* Vertical scrollbar track (background) */
            QScrollBar:vertical {
                border: none;
                background: #464646;
                width: 24px;              /* track width */
                margin: 0px;
            }
            /* Scroll handle (draggable part) */
            QScrollBar::handle:vertical {
                background: #686b64;
                min-height: 25px;
                border-radius: 3px;
                margin: 24px 4px;         /* top/bottom 4px, left/right 4px to center inside track */
                width: 16px;              /* handle width smaller than track */
            }
            QScrollBar::handle:vertical:hover {
                background: #777;
            }
            /* Scroll buttons (up/down) */
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {
                background: #686b64;
                height: 16px;
                border-radius: 3px;
                width: 16px;              /* same as handle */
                margin: 4 4px;            /* center inside track */
            }
            /* Up arrow */
            QScrollBar::sub-line:vertical::up-arrow {
                image: none;
                color: #f0f0f0;
                qproperty-text: "▲";
                font: bold 12px;
            }
            /* Down arrow */
            QScrollBar::add-line:vertical::down-arrow {
                image: none;
                color: #f0f0f0;
                qproperty-text: "▼";
                font: bold 12px;
            }
            /* Empty scrollbar areas */
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # Install custom scrollbars
        # self._setup_custom_scrollbars()

    def _setup_custom_scrollbars(self):
        """Replace default scrollbars with custom nine-slice scrollbars"""
        # Create custom scrollbars
        self.custom_v_scrollbar = NineSliceScrollBar(Qt.Vertical, self)
        self.custom_h_scrollbar = NineSliceScrollBar(Qt.Horizontal, self)
        # Replace the default scrollbars
        self.setVerticalScrollBar(self.custom_v_scrollbar)
        self.setHorizontalScrollBar(self.custom_h_scrollbar)

    def _load_pixmaps(self):
        parts = ['tl','t','tr','l','c','r','bl','b','br']
        self.slices = {}
        self.shadows = {}
        prefix = self.base
        for p in parts:
            fname = _pjoin('resources', f"{prefix}_{p}.tga")
            self.slices[p] = QPixmap(fname)

        # shadows
        #for p in parts:
        #    fname = _pjoin('resources', f"shadow_{p}.tga")
        #    self.shadows[p] = QPixmap(fname)

    def setDisabled(self, disable):
        self.state = 'disabled'
        super().setDisabled(disable)
        self.viewport().update()

    def enterEvent(self, ev):
        if self.isEnabled():
            self.state = 'mouseover'
            self.viewport().update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        if self.isEnabled():
            self.state = 'default'
            self.viewport().update()
        super().leaveEvent(ev)

    def focusInEvent(self, ev):
        if self.isEnabled():
            self.state = 'mousedown'
            self.viewport().update()
        super().focusInEvent(ev)

    def focusOutEvent(self, ev):
        if self.isEnabled():
            self.state = 'default'
            self.viewport().update()
        super().focusOutEvent(ev)

    def paintEvent(self, ev):
        # first paint our nine-slice background
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.TextAntialiasing, False)
        w, h = self.viewport().width(), self.viewport().height()
        s = self.slices

        # TODO: Implement shadows, text is supposed to hide under the shadow on the edges.
        shadows = self.shadows

        # corners
        painter.drawPixmap(0, 0, s['tl'])
        painter.drawPixmap(w - s['tr'].width(), 0, s['tr'])
        painter.drawPixmap(0, h - s['bl'].height(), s['bl'])
        painter.drawPixmap(w - s['br'].width(), h - s['br'].height(), s['br'])

        # edges
        top_rect = QRect(s['tl'].width(), 0, w - s['tl'].width() - s['tr'].width(), s['t'].height())
        bot_rect = QRect(s['bl'].width(), h - s['b'].height(), w - s['bl'].width() - s['br'].width(), s['b'].height())
        left_rect = QRect(0, s['tl'].height(), s['l'].width(), h - s['tl'].height() - s['bl'].height())
        right_rect = QRect(w - s['r'].width(), s['tr'].height(), s['r'].width(), h - s['tr'].height() - s['br'].height())

        painter.drawPixmap(top_rect, s['t'].scaled(top_rect.size()))
        painter.drawPixmap(bot_rect, s['b'].scaled(bot_rect.size()))
        painter.drawPixmap(left_rect, s['l'].scaled(left_rect.size()))
        painter.drawPixmap(right_rect, s['r'].scaled(right_rect.size()))

        # center fill (or tile s['c'])
        cx, cy = s['tl'].width(), s['tl'].height()
        cw = w - s['tl'].width() - s['tr'].width()
        ch = h - s['tl'].height() - s['bl'].height()
        painter.fillRect(cx, cy, cw, ch, QColor('#444d3e'))

        # now let QTextEdit draw its text and cursor
        super().paintEvent(ev)

    def resizeEvent(self, event):
        """Override resize to position custom scrollbars"""
        super().resizeEvent(event)
        # self._position_scrollbars()

    def _position_scrollbars(self):
        """Position scrollbars to align with the text edit boundaries"""
        # Get the widget's total rect
        widget_rect = self.rect()

        vx, vy, vw, vh = self.custom_v_scrollbar.geometry().getRect()

        # sad hardcoded values.
        vx = vx - 20
        vw = vw + 20
        vy = vy + 11
        vh = vh - 23
        self.custom_v_scrollbar.setGeometry(QRect(vx, vy, vw, vh))

        # Position horizontal scrollbar at bottom if needed
        if self.horizontalScrollBarPolicy() != Qt.ScrollBarAlwaysOff:
            # horizontal
            pass


class NoAAFontLabel(QLabel):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, False)  # Disable AA
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())


class _SteamResizeGrip(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._hover = False
        self._down = False
        self._normal = QPixmap(_pjoin('resources', 'resizer.tga'))
        self._hover_pm = QPixmap(_pjoin('resources', 'resizer_mouseover.tga'))
        self._down_pm = QPixmap(_pjoin('resources', 'resizer_mousedown.tga'))

        w = max(16, self._normal.width(), self._hover_pm.width(), self._down_pm.width())
        h = max(16, self._normal.height(), self._hover_pm.height(), self._down_pm.height())
        self.setFixedSize(w, h)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _pixmap(self):
        if self._down and not self._down_pm.isNull():
            return self._down_pm
        if self._hover and not self._hover_pm.isNull():
            return self._hover_pm
        return self._normal

    def paintEvent(self, event):
        pm = self._pixmap()
        if pm.isNull():
            return
        painter = QPainter(self)
        painter.drawPixmap(self.width() - pm.width(), self.height() - pm.height(), pm)
        painter.end()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._down:
            self._hover = False
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._down = True
            self._hover = True
            self.owner._begin_resize(event.globalPos())
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._down:
            self.owner._update_resize(event.globalPos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._down and event.button() == Qt.LeftButton:
            self._down = False
            self.owner._end_resize()
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SbMainWidgetWindow(QWidget):
    HEADER_H = 45
    FOOTER_H = 32
    FIXED_FOOTER_H = 10

    def __init__(self, w = 600, h = 400, title = "SBGUI - Unnamed Window"):
        super().__init__(flags=Qt.FramelessWindowHint)
        self.setWindowTitle(title)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # load window skin slices
        parts = ['tl','t','tr','bl','b','br']
        self.win_slices = {p: QPixmap(_pjoin('resources', f"window_{p}.tga")) for p in parts}
        self.win_slices['htl'] = QPixmap(_pjoin('resources', 'title_tl.tga'))
        self.win_slices['htr'] = QPixmap(_pjoin('resources', 'title_tr.tga'))

        for p in parts:
            self.win_slices[f'c{p}'] = QPixmap(_pjoin('resources', f"inner_{p}.tga"))
        self.win_slices[f'cl'] = QPixmap(_pjoin('resources', f"inner_l.tga"))
        self.win_slices[f'cr'] = QPixmap(_pjoin('resources', f"inner_r.tga"))

        # TODO: Make window size slightly bigger so we can add a fake shadow
        # Real client seems to do this so we need to but for now we dont :(
        self.resize(w,h)

        self._drag_pos = None
        self._resize_start_pos = None
        self._resize_start_size = None
        self.gui_items = {}

        self._add_title_buttons()
        self._add_inputs()
        self._init_resize_support()

    def Register_Item(self, name, obj):
        self.gui_items[name] = obj

    def _init_resize_support(self):
        self._resize_enabled = True
        self.setMouseTracking(True)
        self.setMinimumSize(max(320, self.minimumWidth()), max(220, self.minimumHeight()))
        self._resize_grip = _SteamResizeGrip(self)
        self._reposition_resize_grip()

    def set_resize_enabled(self, enabled):
        self._resize_enabled = bool(enabled)
        if not self._resize_enabled:
            self._end_resize()
            self.setFixedSize(self.size())
        else:
            self.setMinimumSize(max(320, self.minimumWidth()), max(220, self.minimumHeight()))
            self.setMaximumSize(16777215, 16777215)
        self._reposition_resize_grip()

    def _reposition_resize_grip(self):
        if hasattr(self, '_resize_grip') and self._resize_grip:
            self._resize_grip.setVisible(bool(getattr(self, '_resize_enabled', True)))
            if not getattr(self, '_resize_enabled', True):
                return
            self._resize_grip.move(self.width() - self._resize_grip.width() - 6,
                                   self.height() - self._resize_grip.height() - 6)
            self._resize_grip.raise_()

    def _begin_resize(self, global_pos):
        if not getattr(self, '_resize_enabled', True):
            return
        self._resize_start_pos = global_pos
        self._resize_start_size = self.size()

    def _update_resize(self, global_pos):
        if not getattr(self, '_resize_enabled', True):
            return
        if self._resize_start_pos is None or self._resize_start_size is None:
            return
        delta = global_pos - self._resize_start_pos
        new_w = max(self.minimumWidth(), self._resize_start_size.width() + delta.x())
        new_h = max(self.minimumHeight(), self._resize_start_size.height() + delta.y())
        self.resize(new_w, new_h)

    def _end_resize(self):
        self._resize_start_pos = None
        self._resize_start_size = None

    def _footer_height(self):
        return self.FOOTER_H if getattr(self, '_resize_enabled', True) else self.FIXED_FOOTER_H

    def _add_title_buttons(self):
        print(self.windowTitle())
        self.title = QLabel(self.windowTitle(), self)
        self.title.setFont(QFont('Arial', 8, QFont.Bold))
        self.title.setStyleSheet('color:#d8ded3;background:transparent;')
        self.title.setGeometry(20,10,300,30); # draggable
                                               # visible green bar area is painted separately
        close = QPushButton('✕',self); close.setGeometry(self.width()-40,10,30,30); close.clicked.connect(self.close)
        minb  = QPushButton('—',self); minb.setGeometry(self.width()-70,10,30,30);  minb.clicked.connect(self.showMinimized)

        # style bar buttons
        for btn in (close,minb):
            btn.setStyleSheet('background:transparent; color:white; border:none;')

    def _add_inputs(self):
        t = QLabel("You must completely override _add_inputs!", self)
        t.setFont(QFont('Arial', 14, QFont.Bold))
        t.setStyleSheet('color:white;background:transparent;')
        tmpw = int(self.width()/2)
        tmpw = tmpw - len("You must completely override _add_inputs!")
        t.setGeometry(int(self.width()/5),int(self.height()/2),400,30)

    def paintEvent(self,e):
        painter=QPainter(self)
        w,h=self.width(),self.height()
        S=self.win_slices

        # corners
        painter.drawPixmap(0,0,S['tl'])
        painter.drawPixmap(w-S['tr'].width(),0,S['tr'])
        painter.drawPixmap(0,h-S['bl'].height(),S['bl'])
        painter.drawPixmap(w-S['br'].width(),h-S['br'].height(),S['br'])

        # top and bottom edges
        top_h=S['t'].height(); bot_h=S['b'].height()
        painter.drawPixmap(QRect(S['tl'].width(),0,w-S['tl'].width()-S['tr'].width(),top_h),
                           S['t'].scaled(w-S['tl'].width()-S['tr'].width(),top_h))
        painter.drawPixmap(QRect(S['bl'].width(),h-bot_h,w-S['bl'].width()-S['br'].width(),bot_h),
                           S['b'].scaled(w-S['bl'].width()-S['br'].width(),bot_h))

        # sides via gradient
        grad=QLinearGradient(0,S['t'].height(),0,h-S['b'].height())
        grad.setColorAt(0, QColor('#3e4637'))
        grad.setColorAt(1, QColor('#464646'))
        painter.fillRect(0,                       #x
                         S['t'].height(),         #y
                         w,                       #width
                         h-S['t'].height()-S['b'].height(),  #height
                         QBrush(grad))

        # draggable green bar
        # I know this is a really bad way to render this fuck you ben.
        painter.fillRect(5+S['htl'].width(),                     #x
                         10,                                     #y
                         w-S['htr'].width()-20,                  #width
                         S['htr'].height(),                      #height
                         QColor('#5a6a50'))
        painter.fillRect(S['htl'].width()+2,                     #x
                         S['htl'].height()+5,                    #y
                         w-S['htr'].width()-12,                  #width
                         S['htr'].height()+20,                   #height
                         QColor('#5a6a50'))
        painter.drawPixmap(10,10,S['htl'])
        painter.drawPixmap(w-S['htr'].width()-10,10,S['htr'])

        # DO NOT EDIT THE CODE BELOW LESS YOU WANT PAIN
        # DO NOT EDIT THE CODE BELOW LESS YOU WANT PAIN
        # DO NOT EDIT THE CODE BELOW LESS YOU WANT PAIN

        # Filler
        inner_bottom = max(70, h - self._footer_height())
        filler_y = S['ctl'].height()+50
        painter.fillRect(5,                        #x
                         filler_y,                 #y
                         w-S['ctr'].width(),       #width
                         max(0, inner_bottom - filler_y),  #height
                         QColor('#5c5a58'))

        # top
        painter.drawPixmap(5,50,S['ctl'])
        painter.drawPixmap(w-S['ctr'].width()-5,50,S['ctr'])

        # bottom
        painter.drawPixmap(5,inner_bottom-S['cbl'].height(),S['cbl'])
        painter.drawPixmap(w-S['cbr'].width()-5,inner_bottom-S['cbr'].height(),S['cbr'])

        # top bottom (non edges)
        painter.drawPixmap(QRect(15,50, w-20-S['ct'].width(), S['ct'].height()), S['ct'])
        painter.drawPixmap(QRect(15,inner_bottom-S['cb'].height(), w-20-S['ct'].width(), S['ct'].height()), S['cb'])

        # Left and Right (non edges)
        side_y = 50 + S['ct'].height()
        side_h = max(0, inner_bottom - S['cb'].height() - side_y)
        painter.drawPixmap(QRect(5,side_y, S['cl'].width(), side_h), S['cl'])
        painter.drawPixmap(QRect(w-S['cr'].width()-5,side_y, S['cr'].width(), side_h), S['cr'])

        super().paintEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reposition_resize_grip()

    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton and e.y()<self.HEADER_H:
            self._drag_pos=e.globalPos()-self.frameGeometry().topLeft()

    def mouseMoveEvent(self,e):
        if self._drag_pos:
            self.move(e.globalPos()-self._drag_pos)

    def mouseReleaseEvent(self,e):
        self._drag_pos=None


class SbMainQWindow(QMainWindow):
    HEADER_H = 45
    FOOTER_H = 32
    FIXED_FOOTER_H = 10

    def __init__(self, w = 600, h = 400, title = "STEAM - Depot Extractor"):
        super().__init__(flags=Qt.FramelessWindowHint)
        self.setWindowTitle(title)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # load window skin slices
        parts = ['tl','t','tr','bl','b','br']
        self.win_slices = {p: QPixmap(_pjoin('resources', f"window_{p}.tga")) for p in parts}
        self.win_slices['htl'] = QPixmap(_pjoin('resources', 'title_tl.tga'))
        self.win_slices['htr'] = QPixmap(_pjoin('resources', 'title_tr.tga'))

        for p in parts:
            self.win_slices[f'c{p}'] = QPixmap(_pjoin('resources', f"inner_{p}.tga"))
        self.win_slices[f'cl'] = QPixmap(_pjoin('resources', f"inner_l.tga"))
        self.win_slices[f'cr'] = QPixmap(_pjoin('resources', f"inner_r.tga"))

        # TODO: Make window size slightly bigger so we can add a fake shadow
        # Real client seems to do this so we need to but for now we dont :(
        self.resize(w,h)

        self._drag_pos = None
        self._resize_start_pos = None
        self._resize_start_size = None
        self.gui_items = {}

        self._add_title_buttons()
        self._add_inputs()
        self._init_resize_support()

    def Register_Item(self, name, obj):
        self.gui_items[name] = obj

    def setCentralWidget(self, widget):
        super().setCentralWidget(widget)
        self._reposition_resize_grip()

    def _init_resize_support(self):
        self._resize_enabled = True
        self.setMouseTracking(True)
        self.setMinimumSize(max(320, self.minimumWidth()), max(220, self.minimumHeight()))
        self._resize_grip = _SteamResizeGrip(self)
        self._reposition_resize_grip()

    def set_resize_enabled(self, enabled):
        self._resize_enabled = bool(enabled)
        if not self._resize_enabled:
            self._end_resize()
            self.setFixedSize(self.size())
        else:
            self.setMinimumSize(max(320, self.minimumWidth()), max(220, self.minimumHeight()))
            self.setMaximumSize(16777215, 16777215)
        self._reposition_resize_grip()

    def _reposition_resize_grip(self):
        if hasattr(self, '_resize_grip') and self._resize_grip:
            self._resize_grip.setVisible(bool(getattr(self, '_resize_enabled', True)))
            if not getattr(self, '_resize_enabled', True):
                return
            self._resize_grip.move(self.width() - self._resize_grip.width() - 6,
                                   self.height() - self._resize_grip.height() - 6)
            self._resize_grip.raise_()

    def _begin_resize(self, global_pos):
        if not getattr(self, '_resize_enabled', True):
            return
        self._resize_start_pos = global_pos
        self._resize_start_size = self.size()

    def _update_resize(self, global_pos):
        if not getattr(self, '_resize_enabled', True):
            return
        if self._resize_start_pos is None or self._resize_start_size is None:
            return
        delta = global_pos - self._resize_start_pos
        new_w = max(self.minimumWidth(), self._resize_start_size.width() + delta.x())
        new_h = max(self.minimumHeight(), self._resize_start_size.height() + delta.y())
        self.resize(new_w, new_h)

    def _end_resize(self):
        self._resize_start_pos = None
        self._resize_start_size = None

    def _footer_height(self):
        return self.FOOTER_H if getattr(self, '_resize_enabled', True) else self.FIXED_FOOTER_H

    def _add_title_buttons(self):
        # title label
        self.title = QLabel(self.windowTitle(), self)
        self.title.setFont(QFont('Tahoma', 8, QFont.Bold))
        self.title.setStyleSheet('color:#d8ded3;background:transparent;')
        self.title.setFixedHeight(30)

        # close button
        self.close_btn = QPushButton('✕', self)
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setFocusPolicy(Qt.NoFocus)
        self.close_btn.clicked.connect(self.close)

        # minimize button
        self.min_btn = QPushButton('—', self)
        self.min_btn.setFixedSize(30, 30)
        self.min_btn.setFocusPolicy(Qt.NoFocus)
        self.min_btn.clicked.connect(self.showMinimized)

        # style bar buttons (transparent background, no border)
        for btn in (self.close_btn, self.min_btn):
            btn.setStyleSheet('background:transparent; color:white; border:none;')
            btn.setFlat(True)

        # initial positioning (will also be updated on resize)
        self._reposition_title_buttons()

    def _reposition_title_buttons(self):
        """Position title and buttons relative to current window size."""
        margin_right = 10
        spacing = 8
        btn_w = self.close_btn.width()
        btn_h = self.close_btn.height()
        top_y = 10  # same y as your original geometry

        x_close = self.width() - margin_right - btn_w
        x_min = x_close - spacing - btn_w

        # move widgets
        self.close_btn.move(x_close, top_y)
        self.min_btn.move(x_min, top_y)

        # place title at fixed left offset but vertically center inside the 30px header area
        self.title.move(20, top_y)
        self.title.resize(self.width() // 2, btn_h)

        # ensure they are on top so clicks reach them
        self.close_btn.raise_()
        self.min_btn.raise_()
        self.title.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # reposition title/buttons whenever the window changes size
        try:
            self._reposition_title_buttons()
            self._reposition_resize_grip()
        except Exception:
            # defensive: don't let layout errors block resizing
            pass

    def _add_inputs(self):
        t = QLabel("", self)
        t.setFont(QFont('Arial', 14, QFont.Bold))
        t.setStyleSheet('color:white;background:transparent;')
        tmpw = int(self.width()/2)
        tmpw = tmpw - len("You must completely override _add_inputs!")
        t.setGeometry(int(self.width()/5),int(self.height()/2),400,30)

    def paintEvent(self,e):
        painter=QPainter(self)
        w,h=self.width(),self.height()
        S=self.win_slices

        # corners
        painter.drawPixmap(0,0,S['tl'])
        painter.drawPixmap(w-S['tr'].width(),0,S['tr'])
        painter.drawPixmap(0,h-S['bl'].height(),S['bl'])
        painter.drawPixmap(w-S['br'].width(),h-S['br'].height(),S['br'])

        # top and bottom edges
        top_h=S['t'].height(); bot_h=S['b'].height()
        painter.drawPixmap(QRect(S['tl'].width(),0,w-S['tl'].width()-S['tr'].width(),top_h),
                           S['t'].scaled(w-S['tl'].width()-S['tr'].width(),top_h))
        painter.drawPixmap(QRect(S['bl'].width(),h-bot_h,w-S['bl'].width()-S['br'].width(),bot_h),
                           S['b'].scaled(w-S['bl'].width()-S['br'].width(),bot_h))

        # sides via gradient
        grad=QLinearGradient(0,S['t'].height(),0,h-S['b'].height())
        grad.setColorAt(0, QColor('#3e4637'))
        grad.setColorAt(1, QColor('#464646'))
        painter.fillRect(0,                       #x
                         S['t'].height(),         #y
                         w,                       #width
                         h-S['t'].height()-S['b'].height(),  #height
                         QBrush(grad))

        # draggable green bar
        # I know this is a really bad way to render this fuck you ben.
        painter.fillRect(5+S['htl'].width(),                     #x
                         10,                                     #y
                         w-S['htr'].width()-20,                  #width
                         S['htr'].height(),                      #height
                         QColor('#5a6a50'))
        painter.fillRect(S['htl'].width()+2,                     #x
                         S['htl'].height()+5,                    #y
                         w-S['htr'].width()-12,                  #width
                         S['htr'].height()+20,                   #height
                         QColor('#5a6a50'))
        painter.drawPixmap(10,10,S['htl'])
        painter.drawPixmap(w-S['htr'].width()-10,10,S['htr'])

        # DO NOT EDIT THE CODE BELOW LESS YOU WANT PAIN
        # DO NOT EDIT THE CODE BELOW LESS YOU WANT PAIN
        # DO NOT EDIT THE CODE BELOW LESS YOU WANT PAIN

        # Filler
        inner_bottom = max(70, h - self._footer_height())
        filler_y = S['ctl'].height()+50
        painter.fillRect(5,                        #x
                         filler_y,                 #y
                         w-S['ctr'].width(),       #width
                         max(0, inner_bottom - filler_y),  #height
                         QColor('#5c5a58'))

        # top
        painter.drawPixmap(5,50,S['ctl'])
        painter.drawPixmap(w-S['ctr'].width()-5,50,S['ctr'])

        # bottom
        painter.drawPixmap(5,inner_bottom-S['cbl'].height(),S['cbl'])
        painter.drawPixmap(w-S['cbr'].width()-5,inner_bottom-S['cbr'].height(),S['cbr'])

        # top bottom (non edges)
        painter.drawPixmap(QRect(15,50, w-20-S['ct'].width(), S['ct'].height()), S['ct'])
        painter.drawPixmap(QRect(15,inner_bottom-S['cb'].height(), w-20-S['ct'].width(), S['ct'].height()), S['cb'])

        # Left and Right (non edges)
        side_y = 50 + S['ct'].height()
        side_h = max(0, inner_bottom - S['cb'].height() - side_y)
        painter.drawPixmap(QRect(5,side_y, S['cl'].width(), side_h), S['cl'])
        painter.drawPixmap(QRect(w-S['cr'].width()-5,side_y, S['cr'].width(), side_h), S['cr'])

        super().paintEvent(e)

    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton and e.y()<self.HEADER_H:
            self._drag_pos=e.globalPos()-self.frameGeometry().topLeft()

    def mouseMoveEvent(self,e):
        if self._drag_pos:
            self.move(e.globalPos()-self._drag_pos)

    def mouseReleaseEvent(self,e):
        self._drag_pos=None

# Put this in sbgui.py (same file as NineSliceButton, etc.)
# Make sure these are imported at the top of sbgui.py:
# from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt5.QtGui import QPainter, QPixmap, QColor, QBrush
from PyQt5.QtCore import Qt, QRect, QSize

class NineSlicePanel(QWidget):
    """
    Steam-styled 9-slice frame that acts as a container for any child widget.
    Uses the same assets as NineSliceTextEdit:
      resources/<base>_tl.tga, _t.tga, _tr.tga, _l.tga, _c.tga, _r.tga, _bl.tga, _b.tga, _br.tga
    """
    def __init__(self, parent=None, base_name="combo", center_fill="#444d3e", inner_pad=4):
        super().__init__(parent)
        self.base = str(base_name)
        self._center_fill = QColor(center_fill)
        self.inner_pad = int(inner_pad)

        # host for child content
        self._content = QWidget(self)
        self._content.setAttribute(Qt.WA_StyledBackground, False)
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.slices = {}
        self._load_pixmaps()

        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # reasonable minimum so frame doesn’t collapse
        th = self._lh(self.slices.get('t'))
        bh = self._lh(self.slices.get('b'))
        self.setMinimumHeight(max(32, th + bh + 20))

    # ---------- public API ----------
    def setWidget(self, w: QWidget):
        # clear existing
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        # reparent and add
        w.setParent(self._content)
        self._layout.addWidget(w)

    def contentLayout(self) -> QVBoxLayout:
        return self._layout

    # ---------- internals ----------
    def _load_pixmaps(self):
        parts = ['tl','t','tr','l','c','r','bl','b','br']
        for p in parts:
            self.slices[p] = QPixmap(_pjoin('resources', f"{self.base}_{p}.tga"))

    @staticmethod
    def _lw(pm: QPixmap) -> int:
        return 0 if not isinstance(pm, QPixmap) or pm.isNull() else pm.width()

    @staticmethod
    def _lh(pm: QPixmap) -> int:
        return 0 if not isinstance(pm, QPixmap) or pm.isNull() else pm.height()

    def _content_rect(self, w: int, h: int) -> QRect:
        s = self.slices
        left   = max(self._lw(s['tl']), self._lw(s['l']))
        right  = max(self._lw(s['tr']), self._lw(s['r']))
        top    = max(self._lh(s['tl']), self._lh(s['t']))
        bottom = max(self._lh(s['bl']), self._lh(s['b']))

        x  = left   + self.inner_pad
        y  = top    + self.inner_pad
        rw = max(0, w - left - right  - 2*self.inner_pad)
        rh = max(0, h - top  - bottom - 2*self.inner_pad)
        return QRect(x, y, rw, rh)

    # ---------- QWidget overrides ----------
    def resizeEvent(self, ev):
        self._content.setGeometry(self._content_rect(self.width(), self.height()))
        super().resizeEvent(ev)

    def sizeHint(self) -> QSize:
        return QSize(400, 180)

    def minimumSizeHint(self) -> QSize:
        th = self._lh(self.slices.get('t'))
        bh = self._lh(self.slices.get('b'))
        return QSize(120, max(32, th + bh + 20))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        s = self.slices
        w, h = self.width(), self.height()

        # corners
        if not s['tl'].isNull(): p.drawPixmap(0, 0, s['tl'])
        if not s['tr'].isNull(): p.drawPixmap(w - s['tr'].width(), 0, s['tr'])
        if not s['bl'].isNull(): p.drawPixmap(0, h - s['bl'].height(), s['bl'])
        if not s['br'].isNull(): p.drawPixmap(w - s['br'].width(), h - s['br'].height(), s['br'])

        # edges
        if not s['t'].isNull():
            top_rect = QRect(s['tl'].width(), 0,
                             max(0, w - s['tl'].width() - s['tr'].width()),
                             s['t'].height())
            p.drawPixmap(top_rect, s['t'].scaled(top_rect.size()))
        if not s['b'].isNull():
            bot_rect = QRect(s['bl'].width(), h - s['b'].height(),
                             max(0, w - s['bl'].width() - s['br'].width()),
                             s['b'].height())
            p.drawPixmap(bot_rect, s['b'].scaled(bot_rect.size()))
        if not s['l'].isNull():
            left_rect = QRect(0, s['tl'].height(), s['l'].width(),
                              max(0, h - s['tl'].height() - s['bl'].height()))
            p.drawPixmap(left_rect, s['l'].scaled(left_rect.size()))
        if not s['r'].isNull():
            right_rect = QRect(w - s['r'].width(), s['tr'].height(), s['r'].width(),
                               max(0, h - s['tr'].height() - s['br'].height()))
            p.drawPixmap(right_rect, s['r'].scaled(right_rect.size()))

        # center fill or 'c'
        tlw, tlh = s['tl'].width(), s['tl'].height()
        trw, blh = s['tr'].width(), s['bl'].height()
        cx, cy = tlw, tlh
        cw = max(0, w - tlw - trw)
        ch = max(0, h - tlh - blh)
        if not s['c'].isNull():
            p.drawPixmap(QRect(cx, cy, cw, ch), s['c'].scaled(cw, ch))
        else:
            p.fillRect(cx, cy, cw, ch, self._center_fill)

        p.end()


class RoundedClipBox(QWidget):
    """
    Clips its child(ren) to a rounded rectangle. Put any widget inside and its
    visible area will have rounded corners. Good for making the content match
    the NineSlicePanel's inner curvature.
    """
    def __init__(self, parent=None, radius=10, pad=0, antialias=True):
        super().__init__(parent)
        self._radius = int(radius)
        self._pad = int(pad)
        self._antialias = bool(antialias)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(self._pad, self._pad, self._pad, self._pad)
        self._lay.setSpacing(0)

    def setRadius(self, r:int):
        self._radius = int(r)
        self._applyMask()

    def layoutForContent(self) -> QVBoxLayout:
        return self._lay

    def resizeEvent(self, ev):
        self._applyMask()
        super().resizeEvent(ev)

    def _applyMask(self):
        r = self.rect()
        if r.isEmpty():
            return
        path = QPainterPath()
        path.addRoundedRect(QRect(0, 0, r.width(), r.height()), self._radius, self._radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

class SbMessageBox(QDialog):
    HEADER_H = 45
    ICON_W   = 59
    ICON_H   = 59
    ICON_GAP = 12
    LEFT_PAD = 20

    def __init__(self, parent=None, title="Message", text="", icon="warning",
                 buttons=("OK",), default="OK"):
        super().__init__(parent, flags=Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None
        self._title = str(title or "")
        self._text  = str(text or "")
        self._icon  = str(icon or "").lower()
        self._buttons = list(buttons or ("OK",))
        self._default = default

        # --- chrome pixmaps ---
        parts = ['tl','t','tr','bl','b','br']
        self.win_slices = {p: QPixmap(_pjoin('resources', f"window_{p}.tga")) for p in parts}
        self.win_slices['htl'] = QPixmap(_pjoin('resources', 'title_tl.tga'))
        self.win_slices['htr'] = QPixmap(_pjoin('resources', 'title_tr.tga'))
        for k in ("tl","tr","bl","br","t","b","l","r"):
            self.win_slices[f"c{k}"] = QPixmap(_pjoin('resources', f"inner_{k}.tga"))

        # --- icons ---
        self._pix_warning = QPixmap(_pjoin('resources', 'icon_warning.tga'))
        self._pix_info    = QPixmap(_pjoin('resources', 'icon_info.tga'))
        self._pix_error   = QPixmap(_pjoin('resources', 'icon_error.tga'))

        # --- content layout ---
        left_margin  = self.LEFT_PAD + self.ICON_W + self.ICON_GAP
        root = QVBoxLayout(self)
        root.setContentsMargins(left_margin, 70, 20, 20)
        root.setSpacing(12)

        self._lbl = QLabel(self._text, self)
        self._lbl.setWordWrap(True)
        self._lbl.setStyleSheet("color:#ffffff; background:transparent;")
        self._lbl.setFont(QFont("Tahoma", 9, QFont.Bold))
        root.addWidget(self._lbl)

        btns = QHBoxLayout()
        btns.addStretch(1)
        for name in self._buttons:
            b = NineSliceButton(name, base_name="p_button")
            b.setFixedSize(80, 24)
            b.setStyleSheet("font-family: Tahoma; font-size: 9pt; font-weight: bold; color: white;")
            if name.lower() in ("ok","yes","continue"):
                b.clicked.connect(lambda _, n=name: self._accept(n))
            else:
                b.clicked.connect(lambda _, n=name: self._reject(n))
            btns.addWidget(b)
        root.addLayout(btns)

        self._result_text = None
        self._autosize()
        self._center_on_parent_or_screen()

    # -------- static helpers (back again) --------
    @staticmethod
    def warning(parent, title, text):
        box = SbMessageBox(parent, title, text, icon="warning", buttons=("OK",), default="OK")
        box.exec_()
        return box._result_text

    @staticmethod
    def info(parent, title, text):
        box = SbMessageBox(parent, title, text, icon="info", buttons=("OK",), default="OK")
        box.exec_()
        return box._result_text

    @staticmethod
    def critical(parent, title, text):
        box = SbMessageBox(parent, title, text, icon="error", buttons=("OK",), default="OK")
        box.exec_()
        return box._result_text

    # -------- internal helpers --------
    def _get_icon_pm(self) -> QPixmap:
        # try requested icon
        if self._icon == "warning" and not self._pix_warning.isNull():
            return self._pix_warning
        if self._icon == "info" and not self._pix_info.isNull():
            return self._pix_info
        if self._icon == "error" and not self._pix_error.isNull():
            return self._pix_error
        # fallback to warning if available
        if not self._pix_warning.isNull():
            return self._pix_warning
        # nothing found
        return QPixmap()

    def _autosize(self):
        target_w = 480
        self.resize(target_w, 10)
        left, top, right, bottom = self.layout().getContentsMargins()
        avail_w = max(120, target_w - left - right)
        self._lbl.setFixedWidth(avail_w)
        text_h = self._lbl.sizeHint().height()
        chrome_h = 120
        btn_h = 44
        total_h = max(180, text_h + chrome_h + btn_h)
        self.resize(target_w, total_h)

    def _center_on_parent_or_screen(self):
        try:
            if self.parent():
                gp = self.parent().mapToGlobal(self.parent().rect().center())
                self.move(gp.x() - self.width() // 2, gp.y() - self.height() // 2)
                return
        except Exception:
            pass
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else self.geometry()
        self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    # -------- results --------
    def _accept(self, name):
        self._result_text = name
        self.accept()

    def _reject(self, name):
        self._result_text = name
        self.reject()

    # -------- dragging --------
    def mousePressEvent(self, e):
        if e.button()==Qt.LeftButton and e.y()<self.HEADER_H:
            self._drag_pos = e.globalPos()-self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos:
            self.move(e.globalPos()-self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    # -------- paint --------
    def paintEvent(self, e):
        p = QPainter(self)
        w,h = self.width(), self.height()
        S   = self.win_slices

        # corners
        p.drawPixmap(0,0,S['tl'])
        p.drawPixmap(w-S['tr'].width(),0,S['tr'])
        p.drawPixmap(0,h-S['bl'].height(),S['bl'])
        p.drawPixmap(w-S['br'].width(),h-S['br'].height(),S['br'])

        # top + bottom edges
        top_h = S['t'].height(); bot_h = S['b'].height()
        p.drawPixmap(QRect(S['tl'].width(),0,w-S['tl'].width()-S['tr'].width(),top_h),
                     S['t'].scaled(w-S['tl'].width()-S['tr'].width(),top_h))
        p.drawPixmap(QRect(S['bl'].width(),h-bot_h,w-S['bl'].width()-S['br'].width(),bot_h),
                     S['b'].scaled(w-S['bl'].width()-S['br'].width(),bot_h))

        # sides via gradient
        grad = QLinearGradient(0,S['t'].height(),0,h-S['b'].height())
        grad.setColorAt(0, QColor('#3e4637')); grad.setColorAt(1, QColor('#464646'))
        p.fillRect(0, S['t'].height(), w, h-S['t'].height()-S['b'].height(), QBrush(grad))

        # header bars
        p.fillRect(5+S['htl'].width(), 10, w-S['htr'].width()-20, S['htr'].height(), QColor('#5a6a50'))
        p.fillRect(S['htl'].width()+2,  S['htl'].height()+5, w-S['htr'].width()-12, S['htr'].height()+20, QColor('#5a6a50'))
        p.drawPixmap(10,10,S['htl']); p.drawPixmap(w-S['htr'].width()-10,10,S['htr'])

        # title
        p.setFont(QFont('Tahoma', 8, QFont.Bold)); p.setPen(QColor('#d8ded3'))
        p.drawText(QRect(20, 10, w//2, 30), Qt.AlignVCenter|Qt.AlignLeft, self._title)

        # static icon
        pm = self._get_icon_pm()
        if not pm.isNull():
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            icon = pm.scaled(self.ICON_W, self.ICON_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = self.LEFT_PAD
            y = 70
            p.drawPixmap(x, y, icon)

        super().paintEvent(e)




class SbPopUpWindow(QWidget):
    HEADER_H = 45

    def __init__(self, w = 600, h = 400, title = "SBGUI - Unnamed Title", msg = ""):
        super().__init__(flags=Qt.FramelessWindowHint)
        self.setWindowTitle(title)
        self.msg = msg
        self.setAttribute(Qt.WA_TranslucentBackground)

        # load window skin slices
        parts = ['tl','t','tr']
        parts += ['bl','b','br']
        self.win_slices = {p: QPixmap(_pjoin('resources', f"window_{p}.tga")) for p in parts}
        self.win_slices['htl'] = QPixmap(_pjoin('resources', 'title_tl.tga'))
        self.win_slices['htr'] = QPixmap(_pjoin('resources', 'title_tr.tga'))

        # TODO: Make window size slightly bigger so we can add a fake shadow
        # Real client seems to do this so we need to but for now we dont :(
        self.resize(w,h)

        self._drag_pos = None

        self._add_title_buttons()
        self._add_inputs()

    def _add_title_buttons(self):
        self.title = QLabel(self.windowTitle(), self)
        self.title.setFont(QFont('Arial', 8, QFont.Bold))
        self.title.setStyleSheet('color:#d8ded3;background:transparent;')
        self.title.setGeometry(20,10,300,30);  # draggable
                                               # visible green bar area is painted separately
        close = QPushButton('✕',self); close.setGeometry(self.width()-40,10,30,30); close.clicked.connect(self.close)
        minb  = QPushButton('—',self); minb.setGeometry(self.width()-70,10,30,30);  minb.clicked.connect(self.showMinimized)

        # style bar buttons
        for btn in (close,minb):
            btn.setStyleSheet('background:transparent; color:white; border:none;')

    def _add_inputs(self):
        t = QLabel(self.msg, self)
        t.setFont(QFont('Arial', 8, QFont.Bold))
        t.setStyleSheet('color:white;background:transparent;')
        tmpw = int(self.width()/2)
        tmpw = tmpw - len(self.msg)
        t.setGeometry(int(self.width()/5),int(self.height()/2),400,30)

    def paintEvent(self,e):
        painter=QPainter(self)
        w,h=self.width(),self.height()
        S=self.win_slices

        # corners
        painter.drawPixmap(0,0,S['tl'])
        painter.drawPixmap(w-S['tr'].width(),0,S['tr'])
        painter.drawPixmap(0,h-S['bl'].height(),S['bl'])
        painter.drawPixmap(w-S['br'].width(),h-S['br'].height(),S['br'])

        # top and bottom edges
        top_h=S['t'].height(); bot_h=S['b'].height()
        painter.drawPixmap(QRect(S['tl'].width(),0,w-S['tl'].width()-S['tr'].width(),top_h),
                           S['t'].scaled(w-S['tl'].width()-S['tr'].width(),top_h))
        painter.drawPixmap(QRect(S['bl'].width(),h-bot_h,w-S['bl'].width()-S['br'].width(),bot_h),
                           S['b'].scaled(w-S['bl'].width()-S['br'].width(),bot_h))

        # sides via gradient
        grad=QLinearGradient(0,S['t'].height(),0,h-S['b'].height())
        grad.setColorAt(0, QColor('#3e4637'))
        grad.setColorAt(1, QColor('#464646'))
        painter.fillRect(0,                       #x
                         S['t'].height(),         #y
                         w,                       #width
                         h-S['t'].height()-S['b'].height(),  #height
                         QBrush(grad))

        # draggable green bar
        # I know this is a really bad way to render this fuck you ben.
        painter.fillRect(5+S['htl'].width(),                     #x
                         10,                                     #y
                         w-S['htr'].width()-20,                  #width
                         S['htr'].height(),                      #height
                         QColor('#5a6a50'))
        painter.fillRect(S['htl'].width()+2,                     #x
                         S['htl'].height()+5,                    #y
                         w-S['htr'].width()-12,                  #width
                         S['htr'].height()+20,                   #height
                         QColor('#5a6a50'))
        painter.drawPixmap(10,10,S['htl'])
        painter.drawPixmap(w-S['htr'].width()-10,10,S['htr'])

        super().paintEvent(e)

    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton and e.y()<self.HEADER_H:
            self._drag_pos=e.globalPos()-self.frameGeometry().topLeft()

    def mouseMoveEvent(self,e):
        if self._drag_pos:
            self.move(e.globalPos()-self._drag_pos)

    def mouseReleaseEvent(self,e):
        self._drag_pos=None
