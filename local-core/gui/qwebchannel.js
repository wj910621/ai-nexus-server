/*
 * QWebChannel 通信支持
 * 从 PyQt6 分发文件中提取，用于 Python <-> JavaScript 双向通信
 */

var QWebChannelMessageTypes = {
    signal: 1,
    propertyUpdate: 2,
    init: 3,
    idle: 4,
    debug: 5,
    invokeMethod: 6,
    connectToSignal: 7,
    disconnectFromSignal: 8,
    setProperty: 9,
    response: 10,
};

var QWebChannel = function(transport, initCallback)
{
    if (typeof transport !== "object" || typeof transport.send !== "function") {
        console.error("The QWebChannel expects a transport object with a send function and onmessage callback property." +
                      " Given is: transport: " + typeof(transport) + ", transport.send: " + typeof(transport.send));
        return;
    }

    var channel = this;
    this.transport = transport;

    this.send = function(data)
    {
        if (typeof(data) !== "string") {
            data = JSON.stringify(data);
        }
        channel.transport.send(data);
    }

    this.transport.onmessage = function(message)
    {
        var data = message.data;
        if (typeof data === "string") {
            data = JSON.parse(data);
        }
        switch (data.type) {
            case QWebChannelMessageTypes.signal:
                channel.handleSignal(data);
                break;
            case QWebChannelMessageTypes.response:
                channel.handleResponse(data);
                break;
            case QWebChannelMessageTypes.propertyUpdate:
                channel.handlePropertyUpdate(data);
                break;
            default:
                console.error("invalid message received:", message.data);
                break;
        }
    }

    this.execCallbacks = {};
    this.execId = 0;
    this.exec = function(data, callback)
    {
        if (!callback) {
            // if no callback is given, send directly
            channel.send(data);
            return;
        }
        if (channel.execId === Number.MAX_VALUE) {
            channel.execId = Number.MIN_VALUE;
        }
        if (data.hasOwnProperty("id")) {
            console.error("Cannot exec message with property id: " + JSON.stringify(data));
            return;
        }
        data.id = channel.execId++;
        channel.execCallbacks[data.id] = callback;
        channel.send(data);
    };

    this.objects = {};

    this.handleSignal = function(message)
    {
        var object = channel.objects[message.object];
        if (object) {
            object.signalEmitted(message.signal, message.args);
        } else {
            console.warn("Unhandled signal: " + message.object + "::" + message.signal);
        }
    }

    this.handleResponse = function(message)
    {
        if (!message.hasOwnProperty("id")) {
            console.error("Invalid response message received: without id" + JSON.stringify(message));
            return;
        }
        channel.execCallbacks[message.id](message.data);
        delete channel.execCallbacks[message.id];
    }

    this.handlePropertyUpdate = function(message)
    {
        for (var i in message.objects) {
            if (channel.objects[i]) {
                channel.objects[i].propertyUpdate(i, message.objects[i]);
            } else {
                console.warn("Unhandled property update: " + i + "::" + message.data);
            }
        }
        channel.exec({type: QWebChannelMessageTypes.idle});
    }

    this.debug = function(message)
    {
        channel.send({type: QWebChannelMessageTypes.debug, data: message});
    };

    channel.exec({type: QWebChannelMessageTypes.init}, function(data) {
        for (var objectName in data) {
            var object = new QObject(objectName, data[objectName], channel);
        }
        // now unwrap properties, which might reference other registered objects
        for (var objectName in channel.objects) {
            channel.objects[objectName].unwrapProperties();
        }
        if (initCallback) {
            initCallback(channel);
        }
        channel.exec({type: QWebChannelMessageTypes.idle});
    });
};

function QObject(name, data, webChannel)
{
    this.__id = name;
    webChannel.objects[name] = this;

    // List of callbacks that get invoked upon signal emission
    this.__objectSignals__ = {};

    // Cache of all properties, updated when a notify signal is emitted
    this.__propertyCache__ = {};

    var object = this;

    // ----------------------------------------------------------------------

    this.unwrapQObject = function(response)
    {
        if (response instanceof Array) {
            // support list of objects
            var ret = new Array(response.length);
            for (var i = 0; i < response.length; ++i) {
                ret[i] = object.unwrapQObject(response[i]);
            }
            return ret;
        }
        if (!response
            || !response["__QObject*__"]
            || response.id === undefined) {
            return response;
        }

        var objectId = response.id;
        if (webChannel.objects[objectId])
            return webChannel.objects[objectId];

        if (!response.data) {
            console.error("Cannot unwrap unknown QObject " + objectId + " without data.");
            return undefined;
        }

        var qObject = new QObject( objectId, response.data, webChannel );
        qObject.destroyed.connect(function() {
            if (webChannel.objects[objectId] === qObject) {
                delete webChannel.objects[objectId];
                // reset the now deleted QObject to an empty {} object
                // guarding against recursion
                for (var prop in qObject) {
                    delete qObject[prop];
                }
            }
        });
        return qObject;
    }

    this.propertyUpdate = function(signals, propertyMap)
    {
        // update property cache
        for (var propertyIndex in propertyMap) {
            var propertyValue = propertyMap[propertyIndex];
            object.__propertyCache__[propertyIndex] = propertyValue;
        }

        for (var signalName in signals) {
            // Invoke all callbacks, as signalEmitted() does not. The emit signal has only
            // plain arguments, while the signal arg enumeration also contains the parameter names.
            var callbacks = object.__objectSignals__[signalName];
            if (callbacks) {
                var signalArgs = signals[signalName];
                for (var i = 0; i < callbacks.length; ++i) {
                    callbacks[i](signalArgs);
                }
            }

            var signalIndex = signalName.replace("notify(", "").replace(")", "");
            // property value is inline, it might be a new QObject
            if (signalIndex in propertyMap) {
                object.__propertyCache__[signalIndex] = object.unwrapQObject(propertyMap[signalIndex]);
            }
        }
    }

    this.signalEmitted = function(signalName, signalArgs)
    {
        var signal = object.__objectSignals__[signalName];
        if (signal) {
            signal.forEach(function(callback) {
                callback.apply(callback, signalArgs);
            });
        }
    }

    function addSignal(signalData, isPropertyNotifySignal)
    {
        var signalName = signalData[0];
        var signalIndex = signalData[1];
        object[signalName] = {
            connect: function(callback) {
                if (typeof(callback) !== "function") {
                    console.error("Bad callback given to connect to signal " + signalName);
                    return;
                }

                object.__objectSignals__[signalIndex] = object.__objectSignals__[signalIndex] || [];
                object.__objectSignals__[signalIndex].push(callback);

                if (!isPropertyNotifySignal && signalName !== "destroyed") {
                    // only required for "pure" signals, handled separately for properties in propertyUpdate
                    // also note that we never get rid of the connection; the QObject is garbage-collected after we leave this scope
                    object.exec("connectToSignal", { signalIndex: signalIndex });
                }
            },
            disconnect: function(callback) {
                if (typeof(callback) !== "function") {
                    console.error("Bad callback given to disconnect from signal " + signalName);
                    return;
                }
                object.__objectSignals__[signalIndex] = object.__objectSignals__[signalIndex] || [];
                var idx = object.__objectSignals__[signalIndex].indexOf(callback);
                if (idx === -1) {
                    console.error("Cannot find connection of signal " + signalName + " to " + callback.name);
                    return;
                }
                object.__objectSignals__[signalIndex].splice(idx, 1);
                if (!isPropertyNotifySignal && object.__objectSignals__[signalIndex].length === 0) {
                    object.exec("disconnectFromSignal", { signalIndex: signalIndex });
                }
            }
        };
    }

    /**
     * Invokes all callbacks for the given signalindex. Also works for note notify signals.
     */
    function invokeSignalCallbacks(signalName, signalArgs)
    {
        var connections = object.__objectSignals__[signalName];
        if (connections) {
            connections.forEach(function(callback) {
                callback.apply(callback, signalArgs);
            });
        }
    }

    this.propertyUpdate = function(signals, propertyMap)
    {
        // update property cache
        for (var propertyIndex in propertyMap) {
            var propertyValue = propertyMap[propertyIndex];
            object.__propertyCache__[propertyIndex] = propertyValue;
        }

        for (var signalName in signals) {
            // Invoke all callbacks, as signalEmitted() does not. The emit signal has only
            // plain arguments, while the signal arg enumeration also contains the parameter names.
            invokeSignalCallbacks(signalName, signals[signalName]);

            var signalIndex = signalName.replace("notify(", "").replace(")", "");
            // property value is inline, it might be a new QObject
            if (signalIndex in propertyMap) {
                object.__propertyCache__[signalIndex] = object.unwrapQObject(propertyMap[signalIndex]);
            }
        }
    }

    this.signalEmitted = function(signalName, signalArgs)
    {
        invokeSignalCallbacks(signalName, signalArgs);
    }

    function addMethod(methodData)
    {
        var methodName = methodData[0];
        var methodIdx = methodData[1];
        object[methodName] = function() {
            var args = [];
            var callback;
            for (var i = 0; i < arguments.length; ++i) {
                if (typeof arguments[i] === "function")
                    callback = arguments[i];
                else
                    args.push(arguments[i]);
            }

            var retval = { methodIndex: methodIdx, args: args };
            // Insert a callback that returns the value back to the caller
            object.exec("invokeMethod", retval, callback);
        };
    }

    this.exec = function(type, data, callback)
    {
        if (!data) data = {};
        data.type = type;
        data.object = object.__id;
        webChannel.exec(data, callback);
    };

    function bindGetterSetter(propertyInfo)
    {
        var propertyIndex = propertyInfo[0];
        var propertyName = propertyInfo[1];
        var notifySignalData = propertyInfo[2];
        // initialize property cache with current value
        // NOTE: if this is an object, it is not directly unwrapped as it might
        // reference other QObject that we do not know yet
        object.__propertyCache__[propertyIndex] = propertyInfo[3];

        if (notifySignalData) {
            if (notifySignalData[0] === 1) {
                // signal name is optimized away, reconstruct the actual signal name
                notifySignalData[0] = propertyName + "Changed";
            }
            addSignal(notifySignalData, true);
        }

        Object.defineProperty(object, propertyName, {
            configurable: true,
            get: function () {
                var propertyValue = object.__propertyCache__[propertyIndex];
                if (propertyValue === undefined) {
                    // This shouldn't happen
                    console.warn("Undefined value in property cache for property \"" + propertyName + "\" in object " + object.__id);
                }

                return propertyValue;
            },
            set: function(value) {
                if (value === undefined) {
                    console.warn("Property '" + propertyName + "' of object " + object.__id + " set to undefined");
                }
                object.exec("setProperty", {propertyIndex: propertyIndex, value: value});
            }
        });

    }

    // ----------------------------------------------------------------------

    data.methods.forEach(addMethod);
    data.properties.forEach(bindGetterSetter);
    data.signals.forEach(function(signal) { addSignal(signal, false); });

    Object.assign(this, data.enums);
}

//required for use with nodejs
if (typeof module === 'object') {
    module.exports = {
        QWebChannel: QWebChannel
    };
}
