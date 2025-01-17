from __future__ import annotations
import copy
from typing import (Any,
                    Callable,
                    List,
                    Optional,
                    Tuple,
                    Union,
                    cast,
                    TYPE_CHECKING)
import wx
from .element import (Element,
                      FakeElement,
                      LocationallyKeyedElement,
                      MultiElement,
                      PropertyValue,
                      ValidatedPropertyDict)
from . import element_propsvalid as valid
from .element_value import Element_Value, FakeElementValue

if TYPE_CHECKING:
    from .clock_manager import ClockManager
    from gui.layout_canvas import Layout_Canvas

# Global module members for commonly used brushes/pens so that they only need
# to be created once
# TODO: Maybe encapsulate these in some kind of singleton class?

_WHITE_BRUSH: Optional[wx.Brush] = None
_BLACK_PEN: Optional[wx.Pen] = None


# Get the white brush
def GetWhiteBrush() -> wx.Brush:
    global _WHITE_BRUSH
    if _WHITE_BRUSH is None:
        _WHITE_BRUSH = wx.Brush((255, 255, 255))
    return _WHITE_BRUSH


# Get the black pen
def GetBlackPen() -> wx.Pen:
    global _BLACK_PEN
    if _BLACK_PEN is None:
        _BLACK_PEN = wx.Pen(wx.BLACK, 1)
    return _BLACK_PEN


# validates schedule draw style.
# Should be in valid, but I don't want circular dependencies.
def decodeScheduleDraw(name: str, raw: str) -> str:
    if raw in ScheduleLineElement.DRAW_LOOKUP:
        return raw
    raise TypeError(
        f'Parameter {name} must be a valid schedule line draw style'
    )


class ScheduleLineElement(LocationallyKeyedElement):
    # draw line depending on Argos global settings
    DRAW_DEFAULT = 0
    # minimalistic schedule line drawing. No tick marks. Fastest drawing.
    DRAW_CLEAN = 1
    # shows number of local clock cycles taken up by rendering n-1 dots in
    # transaction box
    DRAW_DOTS = 2
    # draws repeating auto_id number over transaction for number of cycles it
    # has no boxes. NEOCLASSICAL
    DRAW_FAST_CLASSIC = 3
    # slowest option
    # draws boxes the size of local ticks regardless of if there are
    # transactions. Also draws repeating text seen in FAST_CLASSIC
    DRAW_CLASSIC = 4

    SHORT_FORMAT_TYPES = ['single_char', 'multi_char']

    # time is relative to current clock.
    _ALL_PROPERTIES = copy.copy(LocationallyKeyedElement._ALL_PROPERTIES)
    # time scale in ticks per pixel
    _ALL_PROPERTIES.update({
        'time_scale': (30.0, valid.validateTimeScale),
        'line_style': ('default', decodeScheduleDraw),
        'short_format': ('single_char', valid.validateString)
    })

    DRAW_LOOKUP = {
        'default': DRAW_DEFAULT,
        'clean': DRAW_CLEAN,
        'dots': DRAW_DOTS,
        'fast_classic': DRAW_FAST_CLASSIC,
        'classic': DRAW_CLASSIC
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        LocationallyKeyedElement.__init__(self, *args, **kwargs)
        self.__buffer = None
        self.__hc = 0
        self.__line_style = \
            self.DRAW_LOOKUP[cast(str, self.GetProperty('line_style'))]

    @staticmethod
    def GetType() -> str:
        return 'schedule_line'

    @staticmethod
    def GetElementProperties() -> ValidatedPropertyDict:
        return ScheduleLineElement._ALL_PROPERTIES

    @staticmethod
    def GetReadOnlyProperties() -> List[str]:
        # we use pixel_offset instead
        return ['t_offset', 'time_scale']

    @staticmethod
    def GetDrawRoutine() -> Callable:
        return ScheduleLineElement.DrawRoutine

    # override to add inheritance stuff
    # period is local period for line element
    # only used when there is a parent schedule giving a t_offset
    def GetProperty(self,
                    key: str,
                    period: Optional[int] = 1) -> PropertyValue:
        # lock horizontal scale to container
        if key[0].isupper():
            return self._properties[key]

        parent = self._parent
        if key == 'dimensions':
            if parent:
                x_dim, _ = cast(Tuple[int, int], parent.GetProperty(key))
                _, y_dim = cast(Tuple[int, int],
                                LocationallyKeyedElement.GetProperty(self,
                                                                     key))
                return x_dim, y_dim
        elif key == 'position':
            if parent:
                x_pos, _ = cast(Tuple[int, int], parent.GetProperty(key))
                _, y_pos = cast(Tuple[int, int],
                                LocationallyKeyedElement.GetProperty(self,
                                                                     key))
                return x_pos, y_pos
        elif key == 'time_scale':
            if parent:
                return parent.GetProperty(key)
            else:
                prop = cast(float, self._properties[key])
                scale = cast(Union[Tuple[float, float], Tuple[int, int]],
                             self.GetProperty('scale_factor'))[0]
                return prop / scale
        elif key == 't_offset':
            if parent:
                # assume parent is schedule (for now)
                assert period is not None
                offset = cast(int, parent.GetProperty('pixel_offset'))
                time_scale = cast(float, parent.GetProperty('time_scale'))
                return -offset * time_scale / period
        return LocationallyKeyedElement.GetProperty(self, key)

    def SetProperty(self, key: str, val: PropertyValue) -> None:
        LocationallyKeyedElement.SetProperty(self, key, val)
        if key == 'line_style':
            assert isinstance(val, str)
            self.__line_style = self.DRAW_LOOKUP[val]

    def GetXDim(self) -> int:
        if self._parent:
            return self._parent.GetXDim()
        else:
            return cast(Tuple[int, int],
                        LocationallyKeyedElement.GetProperty(self,
                                                             'dimensions'))[0]

    def GetYDim(self) -> int:
        return cast(Tuple[int, int],
                    LocationallyKeyedElement.GetProperty(self,
                                                         'dimensions'))[1]

    def GetXPos(self) -> int:
        if self._parent:
            return self._parent.GetXPos()
        else:
            return cast(Tuple[int, int],
                        LocationallyKeyedElement.GetProperty(self,
                                                             'position'))[0]

    def GetYPos(self) -> int:
        return cast(Tuple[int, int],
                    LocationallyKeyedElement.GetProperty(self, 'position'))[1]

    def DrawRoutine(self,
                    pair: Element_Value,
                    dc: wx.DC,
                    canvas: Layout_Canvas,
                    tick: int,
                    time_range: Optional[Tuple[int, int]] = None,
                    render_box: Optional[Tuple[int, int, int, int]] = None,
                    fixed_offset: Optional[Tuple[int, int]] = None) -> None:

        # -Set up draw style-
        line_style = self.__line_style
        dc.SetPen(self._pen)
        # if default, set values based on canvas settings.
        if line_style == self.DRAW_DEFAULT:
            line_style = canvas.GetScheduleLineStyle()
        # set flags to pass to Cython renderer
        renderer_flags = 0
        if line_style == self.DRAW_DOTS:
            renderer_flags = 1
        elif line_style == self.DRAW_CLASSIC:
            renderer_flags = 2

        (c_x, c_y) = cast(Tuple[int, int], self.GetProperty('position'))
        (c_w, c_h) = cast(Tuple[int, int], self.GetProperty('dimensions'))
        xoff, yoff = canvas.GetRenderOffsets()
        if fixed_offset is None:
            (c_x, c_y) = (c_x - xoff, c_y - yoff)
        else:
            c_x = c_x - fixed_offset[0]
            c_y = c_y - fixed_offset[1]

        period = pair.GetClockPeriod()
        t_scale = cast(float, self.GetProperty('time_scale'))
        t_offset = cast(int, self.GetProperty('t_offset', period=period))

        dc.SetBrush(GetWhiteBrush())

        if render_box:
            if render_box[2] == 0 or render_box[3] == 0:
                return  # we're done

            dc.SetClippingRegion(*[int(r) for r in render_box])
            dc.DrawRectangle(int(render_box[0] - 1),
                             int(c_y),
                             int(render_box[2] + 2),
                             int(c_h))
        else:
            dc.SetClippingRegion(int(c_x), int(c_y), int(c_w), int(c_h))
            dc.DrawRectangle(int(c_x), int(c_y), int(c_w), int(c_h))

        if period == -1:
            # we can't render more with an invalid period
            dc.DestroyClippingRegion()
            return

        # if not manually specified render everything
        if not time_range:
            frame_range = self.GetQueryFrame(period)
            time_range = (frame_range[0] + self.__hc,
                          frame_range[1] + self.__hc)

        r = pair.GetTimeRange(time_range)

        # unified clip box
        if render_box:
            clip = render_box[0] - 1, render_box[2] + 2
        else:
            clip = c_x - 1, c_w + 2

        # width of period in pixels
        local_period_width = int(period / t_scale)

        # latest full value rendered
        latest_solid_value = None
        # TODO convert this to an enum instead, take an enum, return an enum
        content_type = cast(str, self.GetProperty('Content'))
        auto_color = (cast(str, self.GetProperty('color_basis_type')),
                      cast(str, self.GetProperty('auto_color_basis')))

        # Draw vertical ticks in background
        if line_style in (self.DRAW_CLASSIC, self.DRAW_FAST_CLASSIC):
            line_end_y = c_y + c_h

            # Draw verical lines at clock boundaries to delimit cycles.
            # These vertical lines can be too close together, so make sure they
            # are at least 1px apart or don't draw them
            end_x = clip[0] + clip[1]
            dc.DrawLine(int(clip[0]), int(c_y), int(end_x), int(c_y))

            current_pixel = \
                (time_range[0] - time_range[0] % period - self.__hc - t_offset * period) / t_scale  # noqa: E501
            width = period / t_scale

            while current_pixel <= end_x:
                start = int(current_pixel)
                dc.DrawLine(int(c_x + start),
                            int(c_y),
                            int(c_x + start),
                            int(line_end_y))
                current_pixel += width

        # Walk through intervals
        for val, interval in r:
            time_width = interval[1] - interval[0]

            # handle phantom elements (width=0)
            if time_width == 0:
                # This is the code that handles drawing out-of-frame
                # elements that extend into our draw area (long elements)
                # IMPORTANT function, however, slows down rendering.
                # optimizing this (if possible) would make things feel faster.

                # we have something we have no info on
                if not latest_solid_value and val is not None:
                    # backtrack
                    # phantom's value is main object's start HC
                    assert isinstance(val, int)
                    if val < interval[0]:
                        # Element outside of view may not still be in cache,
                        # especially if they are long.
                        # This could cause trouble.
                        # Solution: trace the phantoms in the query stage and
                        # query what they point to.
                        # Drawback: performance.
                        qv = pair.GetTimedVal(val)
                        if qv:
                            val, interval = qv
                            latest_solid_value = (val, interval)
                        else:
                            continue
                    else:
                        continue
                else:
                    continue
            else:
                latest_solid_value = (val, interval)

            start_time = interval[0]
            end_time = interval[1]

            time_width = end_time - start_time
            width = int(time_width / t_scale)
            start = \
                int(((start_time - self.__hc) - (t_offset) * period) / t_scale)
            rect = (c_x + start, c_y, width + 1, c_h)

            NOT_MISSING_LOC = False
            short_format = cast(str, self.GetProperty('short_format'))
            canvas.GetRenderer().drawInfoRectangle(
                interval[0],
                self,
                dc,
                canvas,
                rect,
                val,
                NOT_MISSING_LOC,
                content_type,
                auto_color,
                clip,
                schedule_settings=(local_period_width, renderer_flags),
                short_format=short_format
            )

        dc.DestroyClippingRegion()
        self.UnsetNeedsRedraw()

    def GetTime(self) -> int:
        return self.__hc

    def SetTime(self, hc: int) -> None:
        self.__hc = hc

    # Called at  query time and indicates what should be updated
    def GetQueryFrame(self, period: int) -> Tuple[int, int]:
        parent = self._parent
        time_scale = cast(float,
                          parent.GetProperty('time_scale')
                          if parent is not None
                          else self.GetProperty('time_scale'))

        # Optimized version for parent case
        if parent:
            # assume parent is schedule (for now)
            offs = -cast(int, parent.GetProperty('pixel_offset')) * time_scale
            return (int(offs - period),
                    int((offs + period) + self.GetXDim() * time_scale))
        else:
            # in ticks
            offs = cast(int, self.GetProperty('t_offset', period=period))
            return (int((offs - 1) * period),
                    int((offs + 1) * period + self.GetXDim() * time_scale))

    # Generates elements with addresses based on the x coordinate.
    # passes these (fake) elements to the hover preview, which then
    # queries all the needed data fresh.
    # accepts point in local coord
    def DetectCollision(self,
                        pt: Union[Tuple[int, int], wx.Point],
                        pair: Element_Value) -> FakeElementValue:
        mx, my = pt

        period = pair.GetClockPeriod()
        t_scale = cast(float, self.GetProperty('time_scale'))
        offs = cast(int, self.GetProperty('t_offset', period=period)) * period
        offs += int(t_scale * pt[0])

        location = cast(str, self.GetProperty('LocationString'))
        t_offset = offs // period

        fake_element = FakeElement()
        fake_element.SetProperty('LocationString', location)
        fake_element.SetProperty('caption', '')
        fake_element.SetProperty('t_offset', t_offset)
        fake_element.SetProperty('Content', self.GetProperty('Content'))
        fake_element.SetProperty('color_basis_type',
                                 self.GetProperty('color_basis_type'))
        fake_element.SetProperty('auto_color_basis',
                                 self.GetProperty('auto_color_basis'))

        # calculate out coordinates of current transaction
        pos = cast(Tuple[int, int], self.GetProperty('position'))
        fake_x = pt[0] + pos[0] - int((offs % period) / t_scale)
        fake_y = pos[1]
        fake_w = int(period / t_scale)
        fake_h = self.GetYDim()
        fake_element.SetProperty('position', (fake_x, fake_y))
        fake_element.SetProperty('dimensions', (fake_w, fake_h))

        fake_element_val = FakeElementValue(fake_element,
                                            f'{location}@{t_offset}')
        fake_element_val.SetClockPeriod(pair.GetClockPeriod())
        return fake_element_val


ScheduleLineElement._ALL_PROPERTIES['type'] = (ScheduleLineElement.GetType(),
                                               valid.validateString)


# Element shows start times every few cycles.
class ScheduleLineRulerElement(ScheduleLineElement):
    _ALL_PROPERTIES = ScheduleLineElement._ALL_PROPERTIES.copy()

    if 'short_format' in _ALL_PROPERTIES:
        _ALL_PROPERTIES.pop('short_format')

    # special setting not available to user
    DRAW_RULER = 10

    @staticmethod
    def GetType() -> str:
        return 'schedule_line_ruler'

    @staticmethod
    def GetDrawRoutine() -> Callable:
        return ScheduleLineRulerElement.DrawRoutine

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        ScheduleLineElement.__init__(self, *args, **kwargs)
        self.__step = 5

    # very brief rendering function generating time-line
    # I tried just showing transactions and their start time,
    # however it was buggy and added too many special cases and hacks
    # this is quick and simple in comparison
    def DrawRoutine(self,
                    pair: Element_Value,
                    dc: wx.DC,
                    canvas: Layout_Canvas,
                    tick: int,
                    time_range: Optional[Tuple[int, int]] = None,
                    render_box: Optional[Tuple[int, int, int, int]] = None,
                    fixed_offset: Optional[Tuple[int, int]] = None) -> None:

        # render box is disregarded so shift is
        # over-written when acting as a child of a container
        dc.SetPen(self._pen)

        (c_x, c_y) = cast(Tuple[int, int], self.GetProperty('position'))
        (c_w, c_h) = cast(Tuple[int, int], self.GetProperty('dimensions'))
        xoff, yoff = canvas.GetRenderOffsets()
        if not fixed_offset:
            (c_x, c_y) = (c_x - xoff, c_y - yoff)
        else:
            c_x = c_x - fixed_offset[0]
            c_y = c_y - fixed_offset[1]

        t_scale = cast(float, self.GetProperty('time_scale'))
        t_offset = cast(int, self.GetProperty('t_offset',
                                              period=pair.GetClockPeriod()))

        period = pair.GetClockPeriod()

        dc.SetBrush(GetWhiteBrush())

        dc.SetClippingRegion(int(c_x), int(c_y), int(c_w), int(c_h))
        dc.DrawRectangle(int(c_x), int(c_y), int(c_w), int(c_h))

        if period == -1:
            dc.DestroyClippingRegion()
            return

        clip = c_x - 1, c_w + 2

        # figure out step-size based on scale:
        step = self.__step * (int((t_scale + 150) / 100))
        # Set practical limit. No zero-sized steps.
        if step == 0:
            step = 1

        full_interval = period * step
        current_time = t_offset * period
        current_time -= current_time % (period * step)
        width = int(full_interval / t_scale)
        end_time = c_w * t_scale + full_interval + current_time
        while current_time < end_time:
            start = int((current_time - t_offset * period) / t_scale)
            rect = (c_x + start, c_y, width + 1, c_h)
            val = 'C=1 %i' % (current_time / period)
            NOT_MISSING_LOC = False
            canvas.GetRenderer().drawInfoRectangle(
                tick,
                self,
                dc,
                canvas,
                rect,
                val,
                NOT_MISSING_LOC,
                'caption',
                ('', ''),
                clip,
                schedule_settings=(full_interval, self.DRAW_RULER)
            )
            current_time += full_interval

        dc.DestroyClippingRegion()
        self.UnsetNeedsRedraw()

# Container class for Schedule Lines.
# Gives schedule elements the following properties:
# Clock, Width, Time Offset
# Also Controls drawing of schedule lines.


class ScheduleElement(MultiElement):
    _ALL_PROPERTIES = MultiElement._ALL_PROPERTIES.copy()
    _ALL_PROPERTIES.update({'time_scale': (30.0, valid.validateTimeScale)})
    _ALL_PROPERTIES.update({'pixel_offset': (0, valid.validateOffset)})
    _ALL_PROPERTIES.update({'pixels_per_cycle': (0, valid.validateTimeScale)})
    _ALL_PROPERTIES.update({'cycle_offset': (0, valid.validateOffset)})
    _ALL_PROPERTIES.update({'clock': ('', valid.validateString)})

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        MultiElement.__init__(self, *args, **kwargs)
        self.__buffer: Optional[wx.Bitmap] = None
        self.__temp_buffer: Optional[wx.Bitmap] = None
        self.__dc = wx.MemoryDC()  # store our own DC
        self.__temp_dc = wx.MemoryDC()
        self.__graphics_dc: Optional[wx.GCDC] = None

        self.__old_dimensions: Optional[Tuple[int, int]] = None
        self.__last_hc: Optional[int] = None
        self.__old_period = 1
        self.__remainder_dp = 0.0
        # Check that the clock name (if any) is valid.
        clock_name = cast(str, self.GetProperty('clock'))
        if clock_name:
            if self.__FindClockOrWarn(clock_name) is not None:
                # If it is, go ahead and refresh the scale and offset
                # parameters
                self.__RefreshProperty('pixels_per_cycle')
                self.__RefreshProperty('cycle_offset')

    @staticmethod
    def GetType() -> str:
        return 'schedule'

    @staticmethod
    def IsDrawable() -> bool:
        return True

    @staticmethod
    def IsSelectable() -> bool:
        return False

    @staticmethod
    def GetElementProperties() -> ValidatedPropertyDict:
        return ScheduleElement._ALL_PROPERTIES

    @staticmethod
    def GetReadOnlyProperties() -> List[str]:
        # we use pixel_offset instead
        return ['t_offset', 'time_scale', 'pixel_offset']

    @staticmethod
    def GetDrawRoutine() -> Callable:
        return ScheduleElement.DrawRoutine

    def __FindClockOrWarn(
        self,
        clock_name: str
    ) -> Optional[ClockManager.ClockDomain]:
        clock_domain = None
        assert self._layout is not None
        if self._layout.HasContext():
            for context in self._layout.lay_cons:
                clock_manager = context.dbhandle.database.clock_manager
                if clock_manager.doesClockNameExist(clock_name):
                    clock_domain = \
                        clock_manager.getClockDomainByName(clock_name)
                    break
        if clock_domain is None:
            print(f'Warning: Could not find clock named {clock_name}. '
                  'Falling back to time_scale value.')
        return clock_domain

    def __RefreshProperty(self, key: str) -> None:
        self.SetProperty(key, self.GetProperty(key))

    def GetProperty(self,
                    key: str,
                    period: Optional[int] = None) -> PropertyValue:
        if key == 'pixel_offset' or key == 'pixels_per_cycle':
            scale_factor = \
                cast(Union[Tuple[float, float], Tuple[int, int]],
                     MultiElement.GetProperty(self, 'scale_factor'))[0]
            return round(
                cast(int, MultiElement.GetProperty(self, key)) * scale_factor
            )
        elif key == 'time_scale':
            scale_factor = \
                cast(Union[Tuple[float, float], Tuple[int, int]],
                     MultiElement.GetProperty(self, 'scale_factor'))[0]
            return cast(float,
                        MultiElement.GetProperty(self, key)) / scale_factor
        return MultiElement.GetProperty(self, key)

    def SetProperty(self, key: str, val: PropertyValue) -> None:
        MultiElement.SetProperty(self, key, val)
        if key == 'clock':
            if val:
                self.__RefreshProperty('pixels_per_cycle')
                self.__RefreshProperty('cycle_offset')
        elif key == 'pixels_per_cycle':
            # Need to add the ability for an element to access the clock
            # manager...
            clock_name = cast(str, self.GetProperty('clock'))
            clock_domain = self.__FindClockOrWarn(clock_name)
            val = cast(float, val)
            if clock_domain is not None and val != 0:
                time_scale = clock_domain.tick_period / val
                self.SetProperty('time_scale', time_scale)
                self.__RefreshProperty('cycle_offset')
        elif key == 'cycle_offset':
            # Need to add the ability for an element to access the clock
            # manager...
            clock_name = cast(str, self.GetProperty('clock'))
            clock_domain = self.__FindClockOrWarn(clock_name)
            if clock_domain is not None:
                val = cast(float, val)
                time_scale = cast(float, self.GetProperty('time_scale'))
                pixel_offset = int(clock_domain.tick_period * val / time_scale)
                self.SetProperty('pixel_offset', pixel_offset)

    def __ReinitializeBuffer(self,
                             canvas: Layout_Canvas,
                             width: int,
                             height: int) -> None:
        self.__buffer = wx.Bitmap(canvas.MAX_ZOOM * width,
                                  canvas.MAX_ZOOM * height)
        self.__temp_buffer = wx.Bitmap(canvas.MAX_ZOOM * width,
                                       canvas.MAX_ZOOM * height)
        self.__SwapBuffers(canvas)

    def __SwapBuffers(self, canvas: Layout_Canvas) -> None:
        assert self.__buffer is not None
        assert self.__temp_buffer is not None
        self.__buffer, self.__temp_buffer = self.__temp_buffer, self.__buffer
        self.__dc.SelectObject(self.__buffer)
        self.__temp_dc.SelectObject(self.__temp_buffer)
        self.__graphics_dc = wx.GCDC(self.__dc)
        self.__graphics_dc.SetFont(self.__dc.GetFont())
        self.__graphics_dc.SetLogicalScale(canvas.MAX_ZOOM, canvas.MAX_ZOOM)

    def DrawRoutine(self,
                    pair: Element_Value,
                    dc: wx.DC,
                    canvas: Layout_Canvas,
                    tick: int) -> None:
        children = self.GetChildren()
        if not children:
            # our work is done here
            return

        (c_x, c_y) = cast(Tuple[int, int], self.GetProperty('position'))
        (c_w, c_h) = cast(Tuple[int, int], self.GetProperty('dimensions'))
        absolute_x = c_x
        xoff, yoff = canvas.GetRenderOffsets()
        (c_x, c_y) = (c_x - xoff, c_y - yoff)

        window_max = dc.GetSize()
        if window_max[0] < c_x or window_max[1] < c_y:
            return  # all out of bounds

        # some kind of huge number
        highest_y = 100000000000
        lowest_y = 0

        pairs = []
        largest_period = 0

        # @todo This is imporper. HasChanged refers to layout state, not
        #  drawing state. Reading HasChanged to determine if an update should
        #  be done is not appropriate. Writing MarkAsUnchanged() will break
        #  other frames using the same layout AND break "modified layout"
        #  functionality

        full_update = self.HasChanged() or self.NeedsRedraw()
        # --Pre-Render Cycle--
        # * Poll children for changes
        # * Populate our pairs list (could be moved outside render function)
        # * Find largest period
        # * Find bounds of schedule lines
        for child in children:
            # poll for changes
            if child.HasChanged() or child.NeedsRedraw():
                full_update = True
                child._MarkAsUnchanged()
                child.UnsetNeedsRedraw()

            ycpos = child.GetYPos()
            lowest_y_tmp = ycpos + child.GetYDim()

            # set highest and lowest y values for element bounds
            if lowest_y_tmp > lowest_y:
                lowest_y = lowest_y_tmp
            if ycpos < highest_y:
                highest_y = ycpos

            # collect pairs from elements
            assert isinstance(child, LocationallyKeyedElement)
            new_pair = canvas.context.GetElementPair(child)
            assert new_pair is not None
            pair = new_pair
            pairs.append(pair)
            possible_period = pair.GetClockPeriod()
            if possible_period > largest_period:
                largest_period = possible_period
        first_child = cast(ScheduleLineElement, children[0])
        hc = first_child.GetTime()
        # ticks per pixel
        t_scale = cast(float, first_child.GetProperty('time_scale'))
        tick_offset = cast(int, first_child.GetProperty('t_offset'))
        frame_range = (int(tick_offset),
                       int(tick_offset + self.GetXDim() * t_scale))

        # Determine update type
        if self.__old_period != largest_period:
            full_update = True
            self.__old_period = largest_period
        if self.__last_hc is None:
            full_update = True
            self.__last_hc = hc

        # Find deltas
        d_t = hc - self.__last_hc
        d_p = -d_t / t_scale + self.__remainder_dp
        i_d_p = int(d_p)

        # convert pixel to time space:
        # if d_t is wider than window, do full update
        if d_t > (frame_range[1] - frame_range[0]):
            start_range = frame_range[0] + hc
            end_range = frame_range[1] + hc
            full_update = True
        else:
            # update smaller than window, just fill what is needed
            if d_t > 0:
                # forward motion. need high range
                start_range = frame_range[1] + self.__last_hc - largest_period
                end_range = frame_range[1] + hc + largest_period
            elif d_t < 0:
                # back, low range needed
                start_range = frame_range[0] + hc - largest_period
                end_range = frame_range[0] + largest_period + self.__last_hc
            else:
                start_range = hc
                end_range = hc

        sched_height = lowest_y - highest_y
        # Execute the set update type
        if self.__buffer is None:
            time_range = None  # draw full frame
            clip_region = None
            self.__dc.SetFont(dc.GetFont())
            self.__ReinitializeBuffer(canvas, c_w, sched_height)
            self.__dc.Clear()
        elif full_update:
            time_range = None
            clip_region = None
            if self.__old_dimensions != (c_w, sched_height):
                self.__dc.SetFont(dc.GetFont())
                # we need to make a new buffer
                self.__ReinitializeBuffer(canvas, c_w, sched_height)
            self.__dc.Clear()
        else:
            # make box
            box_size = (c_w, sched_height)

            clip_region = None
            if i_d_p < 0:
                # moving forward (to left) need to fill in forward
                clip_region = (c_w + i_d_p, 0, -i_d_p, box_size[1])
            else:
                # moving backward (to right), need to fill in back
                clip_region = (0, 0, i_d_p, box_size[1])

            time_range = (start_range, end_range)
            if i_d_p < 0:
                sub_x = -canvas.MAX_ZOOM * i_d_p
                sub_width = self.__buffer.GetWidth() - sub_x
                dest_x = 0
            else:
                sub_x = 0
                dest_x = canvas.MAX_ZOOM * i_d_p
                sub_width = self.__buffer.GetWidth() - dest_x

            assert self.__graphics_dc is not None
            self.__graphics_dc.SetLogicalScale(1, 1)
            self.__temp_dc.Blit(int(dest_x),
                                0,
                                int(sub_width),
                                int(self.__buffer.GetHeight()),
                                self.__dc, int(sub_x),
                                0)
            self.__SwapBuffers(canvas)
            self.__graphics_dc.SetLogicalScale(canvas.MAX_ZOOM,
                                               canvas.MAX_ZOOM)

        assert self.__buffer is not None

        # --Render Loop--
        for child_idx, child in enumerate(children):
            child = cast(ScheduleLineElement, child)
            assert self.__graphics_dc is not None
            child.DrawRoutine(pairs[child_idx],
                              self.__graphics_dc,
                              canvas,
                              tick,
                              time_range,
                              clip_region,
                              fixed_offset=(absolute_x, highest_y))

        # Calculate the blit destination location, width, and height
        update_box = canvas.GetScaledUpdateRegion()
        update_top_left = update_box.GetTopLeft()
        update_bottom_right = update_box.GetBottomRight()
        sched_x = c_x
        sched_y = highest_y - yoff
        sched_x_end = sched_x + c_w
        sched_y_end = sched_y + sched_height
        blit_x = max(sched_x, update_top_left[0])
        blit_y = max(sched_y, update_top_left[1])
        blit_x_end = min(update_bottom_right[0], sched_x_end)
        blit_y_end = min(update_bottom_right[1], sched_y_end)
        blit_width = max(0, blit_x_end - blit_x)
        blit_height = max(0, blit_y_end - blit_y)

        # Calculate offsets, width, and height within our buffer
        blit_x_offset = canvas.MAX_ZOOM * (blit_x - sched_x)
        blit_y_offset = canvas.MAX_ZOOM * (blit_y - sched_y)
        blit_src_width = canvas.MAX_ZOOM * blit_width
        blit_src_height = canvas.MAX_ZOOM * blit_height

        assert blit_src_width <= self.__buffer.GetWidth()
        assert blit_src_height <= self.__buffer.GetHeight()

        dc.StretchBlit(int(blit_x),
                       int(blit_y),
                       int(blit_width),
                       int(blit_height),
                       self.__dc,
                       int(blit_x_offset),
                       int(blit_y_offset),
                       int(blit_src_width),
                       int(blit_src_height))

        # draw vertical line at offset 0
        dc.SetPen(GetBlackPen())
        zero_x_coord = c_x - tick_offset / t_scale
        dc.DrawLine(int(zero_x_coord),
                    int(highest_y - yoff),
                    int(zero_x_coord),
                    int(lowest_y - yoff))

        if i_d_p != 0:
            self.__remainder_dp = d_p - i_d_p
            # only update if we've progressed the pixels. This cuts down on
            # rounding error.
            self.__last_hc = hc
        self.__old_dimensions = (c_w, sched_height)

        self._MarkAsUnchanged()
        self.UnsetNeedsRedraw()

    # Detect collision with children (they are likely not drawn)
    #  @param pt Point to test
    #  @return First child which includes pt
    def DetectCollision(
        self,
        pt: Union[Tuple[int, int], wx.Point]
    ) -> Optional[Element]:
        mx, my = pt

        for child in self.GetChildren():
            x, y = cast(Tuple[int, int], child.GetProperty('position'))
            w, h = cast(Tuple[int, int], child.GetProperty('dimensions'))

            if x <= mx <= (x + w) and y <= my <= (y + h):
                return child

        return None  # No collision detected

    def AddChild(self, child: Element) -> None:
        if not isinstance(child, ScheduleLineElement):
            raise Exception(
                'Children of ScheduleElement must be ScheduleLineElements or '
                'descendants.'
            )

        MultiElement.AddChild(self, child)
        # grab render control
        child.EnableDraw(False)


ScheduleElement._ALL_PROPERTIES['type'] = (ScheduleElement.GetType(),
                                           valid.validateString)
